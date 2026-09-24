"use client";

import React, { useState, useCallback, useEffect } from "react";
import Link from "next/link";
import { ArrowRight, Menu, X, Sparkles } from "lucide-react";
import { useLanguage } from "@/lib/i18n/LanguageContext";
import LanguageSwitcher from "@/components/common/LanguageSwitcher";
import UserMenu from "@/components/auth/UserMenu";

/* ═══ AgriWise Floating Capsule Island Navigation ═════════════════
   - Logo removed from top bar as requested (clean typographic wordmark)
   - High-contrast obsidian glass capsule floating at the top of the viewport
   - Interactive segmented pill navigation tabs with active tracking
   - Fluid cubic-bezier transitions & emerald breathing indicator
   - Dynamic Multi-Language (EN / AR / FR) & RTL support
   ═══════════════════════════════════════════════════════════════ */

export default function HomeNav() {
  const { t, isRtl } = useLanguage();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [activeSection, setActiveSection] = useState<string>("");
  const [scrolled, setScrolled] = useState(false);

  const navItems = [
    { label: t.nav.perception, href: "#perception" },
    { label: t.nav.reasoning, href: "#reasoning" },
    { label: t.nav.scale, href: "#scale" },
    { label: t.nav.architecture, href: "#architecture" },
    { label: t.nav.platforms, href: "#platforms" },
    { label: t.nav.deploy, href: "#deployment" },
  ];

  useEffect(() => {
    if (typeof window === "undefined") return;
    const sectionIds = ["perception", "reasoning", "scale", "architecture", "platforms", "deployment"];
    
    const handleScroll = () => {
      const scrollPosition = window.scrollY + 180;
      setScrolled(window.scrollY > 20);

      for (let i = sectionIds.length - 1; i >= 0; i--) {
        const el = document.getElementById(sectionIds[i]);
        if (el && el.offsetTop <= scrollPosition) {
          setActiveSection(`#${sectionIds[i]}`);
          return;
        }
      }
      setActiveSection("");
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const toggleMobile = useCallback(() => {
    setMobileOpen((prev) => !prev);
  }, []);

  const closeMobile = useCallback(() => {
    setMobileOpen(false);
  }, []);

  return (
    <header
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        zIndex: 1000,
        width: "100%",
        padding: scrolled ? "8px 16px" : "14px 16px",
        pointerEvents: "none",
        transition: "padding 0.3s cubic-bezier(0.16, 1, 0.3, 1)",
      }}
    >
      {/* Floating Glass Island Capsule */}
      <div
        className="nav-floating-capsule"
        style={{
          maxWidth: "1240px",
          margin: "0 auto",
          height: "60px",
          background: scrolled
            ? "rgba(6, 16, 10, 0.88)"
            : "rgba(6, 16, 10, 0.72)",
          backdropFilter: "blur(28px)",
          WebkitBackdropFilter: "blur(28px)",
          border: scrolled
            ? "1px solid rgba(34, 197, 94, 0.25)"
            : "1px solid rgba(255, 255, 255, 0.1)",
          borderRadius: "9999px",
          boxShadow: scrolled
            ? "0 20px 50px -10px rgba(0, 0, 0, 0.8), 0 0 25px rgba(34, 197, 94, 0.12)"
            : "0 16px 40px -10px rgba(0, 0, 0, 0.6)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 10px 0 22px",
          pointerEvents: "auto",
          transition: "all 0.3s cubic-bezier(0.16, 1, 0.3, 1)",
        }}
      >
        {/* Left: Pure Modern Typographic Brand (Logo Removed from Top Bar) */}
        <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
          <Link
            href="/"
            aria-label="AgriWise Home"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "8px",
              textDecoration: "none",
            }}
          >
            {/* Typographic wordmark */}
            <span
              className="font-heading"
              style={{
                fontSize: "19px",
                fontWeight: 800,
                letterSpacing: "-0.025em",
                color: "#FFFFFF",
                lineHeight: 1,
              }}
            >
              AGRIWISE
            </span>

            {/* Glowing Status Dot */}
            <span
              style={{
                width: "6px",
                height: "6px",
                borderRadius: "50%",
                background: "#22c55e",
                boxShadow: "0 0 10px #22c55e",
                display: "inline-block",
              }}
            />
          </Link>

          {/* Subtitle Pill Badge */}
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "5px",
              padding: "3px 9px",
              borderRadius: "9999px",
              background: "rgba(34, 197, 94, 0.08)",
              border: "1px solid rgba(34, 197, 94, 0.22)",
              fontSize: "10px",
              fontFamily: "var(--font-mono)",
              color: "#22c55e",
              letterSpacing: "0.08em",
            }}
            className="nav-org-link"
          >
            <Sparkles size={11} />
            <span>{t.nav.worldModel}</span>
          </div>
        </div>

        {/* Center: Segmented Floating Pill Navigation */}
        <nav
          className="desktop-nav-menu"
          aria-label="Main Navigation"
          style={{
            display: "flex",
            alignItems: "center",
            gap: "4px",
            background: "rgba(255, 255, 255, 0.03)",
            padding: "4px",
            borderRadius: "9999px",
            border: "1px solid rgba(255, 255, 255, 0.05)",
          }}
        >
          {navItems.map((item) => {
            const isActive = activeSection === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className="transition-smooth"
                style={{
                  padding: "7px 16px",
                  borderRadius: "9999px",
                  fontSize: "13px",
                  fontWeight: isActive ? 700 : 500,
                  fontFamily: "var(--font-heading)",
                  color: isActive ? "#22c55e" : "#94A3B8",
                  background: isActive ? "rgba(34, 197, 94, 0.16)" : "transparent",
                  border: isActive
                    ? "1px solid rgba(34, 197, 94, 0.35)"
                    : "1px solid transparent",
                  boxShadow: isActive ? "0 0 14px rgba(34, 197, 94, 0.2)" : "none",
                  textDecoration: "none",
                  letterSpacing: "-0.01em",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                }}
                onMouseEnter={(e) => {
                  if (!isActive) {
                    e.currentTarget.style.color = "#FFFFFF";
                    e.currentTarget.style.background = "rgba(255, 255, 255, 0.05)";
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isActive) {
                    e.currentTarget.style.color = "#94A3B8";
                    e.currentTarget.style.background = "transparent";
                  }
                }}
              >
                {isActive && (
                  <span
                    style={{
                      width: "5px",
                      height: "5px",
                      borderRadius: "50%",
                      backgroundColor: "#22c55e",
                      boxShadow: "0 0 6px #22c55e",
                    }}
                  />
                )}
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Right: Modern Action Gateways & Language Switcher */}
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          {/* Language Switcher Capsule */}
          <LanguageSwitcher variant="capsule" />

          {/* User Auth Profile Menu */}
          <UserMenu />

          <Link
            href="/farm/new"
            className="hover-lift transition-smooth"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              fontSize: "13px",
              fontWeight: 700,
              fontFamily: "var(--font-heading)",
              color: "#05070B",
              background: "#22c55e",
              padding: "9px 20px",
              borderRadius: "9999px",
              textDecoration: "none",
              boxShadow: "0 4px 20px rgba(34, 197, 94, 0.35)",
            }}
          >
            <span>{t.nav.analyzeField}</span>
            <ArrowRight
              size={14}
              style={{
                transform: isRtl ? "rotate(180deg)" : "none",
                transition: "transform 0.2s ease",
              }}
            />
          </Link>

          {/* Mobile hamburger button */}
          <button
            onClick={toggleMobile}
            aria-label="Toggle navigation"
            className="mobile-nav-toggle-btn"
            style={{
              background: "rgba(255, 255, 255, 0.05)",
              border: "1px solid rgba(255, 255, 255, 0.1)",
              borderRadius: "50%",
              width: "38px",
              height: "38px",
              color: "#94a3b8",
              cursor: "pointer",
              padding: 0,
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            {mobileOpen ? <X size={18} /> : <Menu size={18} />}
          </button>
        </div>
      </div>

      {/* Mobile Drawer (Floating Glass Dropdown) */}
      {mobileOpen && (
        <div
          style={{
            maxWidth: "1240px",
            margin: "8px auto 0",
            background: "rgba(6, 16, 10, 0.96)",
            backdropFilter: "blur(28px)",
            WebkitBackdropFilter: "blur(28px)",
            border: "1px solid rgba(34, 197, 94, 0.25)",
            borderRadius: "20px",
            padding: "20px",
            display: "flex",
            flexDirection: "column",
            gap: "14px",
            boxShadow: "0 24px 60px rgba(0, 0, 0, 0.9)",
            pointerEvents: "auto",
          }}
        >
          {/* Mobile Language Selector */}
          <LanguageSwitcher variant="mobile" />

          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              onClick={closeMobile}
              style={{
                fontSize: "15px",
                color: activeSection === item.href ? "#22c55e" : "#e2e8f0",
                textDecoration: "none",
                fontWeight: activeSection === item.href ? 700 : 500,
                padding: "8px 12px",
                borderRadius: "8px",
                background: activeSection === item.href ? "rgba(34, 197, 94, 0.1)" : "transparent",
                fontFamily: "var(--font-heading)",
              }}
            >
              {item.label}
            </Link>
          ))}
          <div style={{ paddingTop: "12px", borderTop: "1px solid rgba(255, 255, 255, 0.08)" }}>
            <Link
              href="#deployment"
              onClick={closeMobile}
              style={{
                textAlign: "center",
                display: "block",
                padding: "11px",
                fontSize: "14px",
                color: "#cbd5e1",
                border: "1px solid rgba(255, 255, 255, 0.12)",
                borderRadius: "9999px",
                textDecoration: "none",
                fontWeight: 600,
                fontFamily: "var(--font-heading)",
              }}
            >
              {t.nav.forEnterprise}
            </Link>
          </div>
        </div>
      )}
    </header>
  );
}

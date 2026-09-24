"use client";

import React, { useState, useRef, useEffect } from "react";
import { Globe, Check, ChevronDown } from "lucide-react";
import { useLanguage } from "@/lib/i18n/LanguageContext";
import type { Locale } from "@/lib/i18n/types";

interface LanguageSwitcherProps {
  variant?: "capsule" | "footer" | "mobile";
  className?: string;
}

export default function LanguageSwitcher({
  variant = "capsule",
  className = "",
}: LanguageSwitcherProps) {
  const { locale, setLocale, locales, isRtl } = useLanguage();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleSelect = (code: Locale) => {
    setLocale(code);
    setIsOpen(false);
  };

  const currentMeta = locales[locale];

  if (variant === "mobile") {
    return (
      <div
        className={`language-switcher-mobile ${className}`}
        style={{
          display: "flex",
          gap: "8px",
          padding: "6px",
          background: "rgba(255, 255, 255, 0.04)",
          borderRadius: "12px",
          border: "1px solid rgba(255, 255, 255, 0.08)",
        }}
      >
        {(["en", "ar", "fr"] as Locale[]).map((code) => {
          const item = locales[code];
          const isActive = locale === code;
          return (
            <button
              key={code}
              onClick={() => setLocale(code)}
              style={{
                flex: 1,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "6px",
                padding: "8px 12px",
                borderRadius: "8px",
                fontSize: "13px",
                fontFamily: code === "ar" ? "'IBM Plex Sans Arabic', sans-serif" : "var(--font-heading)",
                fontWeight: isActive ? 700 : 500,
                color: isActive ? "#22c55e" : "#94A3B8",
                background: isActive ? "rgba(34, 197, 94, 0.16)" : "transparent",
                border: isActive ? "1px solid rgba(34, 197, 94, 0.35)" : "1px solid transparent",
                cursor: "pointer",
                transition: "all 0.2s ease",
              }}
            >
              <span>{item.flag}</span>
              <span>{item.nativeName}</span>
            </button>
          );
        })}
      </div>
    );
  }

  return (
    <div
      ref={dropdownRef}
      className={`language-switcher-root ${className}`}
      style={{
        position: "relative",
        display: "inline-block",
        zIndex: 50,
      }}
    >
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        aria-label="Select Language"
        aria-expanded={isOpen}
        className="hover-lift transition-smooth"
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "6px",
          padding: variant === "footer" ? "6px 14px" : "6px 12px",
          borderRadius: "9999px",
          background: isOpen ? "rgba(34, 197, 94, 0.15)" : "rgba(255, 255, 255, 0.04)",
          border: isOpen ? "1px solid rgba(34, 197, 94, 0.4)" : "1px solid rgba(255, 255, 255, 0.1)",
          color: isOpen ? "#22c55e" : "#CBD5E1",
          fontSize: "12px",
          fontWeight: 600,
          fontFamily: locale === "ar" ? "'IBM Plex Sans Arabic', sans-serif" : "var(--font-heading)",
          cursor: "pointer",
          userSelect: "none",
        }}
      >
        <Globe size={13} style={{ color: "#22c55e", flexShrink: 0 }} />
        <span>{currentMeta.nativeName}</span>
        <ChevronDown
          size={12}
          style={{
            transform: isOpen ? "rotate(180deg)" : "rotate(0)",
            transition: "transform 0.2s ease",
            opacity: 0.7,
          }}
        />
      </button>

      {/* Floating Glass Dropdown Menu */}
      {isOpen && (
        <div
          style={{
            position: "absolute",
            top: "calc(100% + 8px)",
            [isRtl ? "left" : "right"]: 0,
            minWidth: "160px",
            background: "rgba(6, 16, 10, 0.95)",
            backdropFilter: "blur(24px)",
            WebkitBackdropFilter: "blur(24px)",
            border: "1px solid rgba(34, 197, 94, 0.25)",
            borderRadius: "14px",
            padding: "6px",
            boxShadow: "0 16px 40px rgba(0, 0, 0, 0.8), 0 0 20px rgba(34, 197, 94, 0.1)",
            display: "flex",
            flexDirection: "column",
            gap: "2px",
          }}
        >
          {(["en", "ar", "fr"] as Locale[]).map((code) => {
            const item = locales[code];
            const isActive = locale === code;
            return (
              <button
                key={code}
                type="button"
                onClick={() => handleSelect(code)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "8px 12px",
                  borderRadius: "8px",
                  background: isActive ? "rgba(34, 197, 94, 0.16)" : "transparent",
                  border: "none",
                  color: isActive ? "#22c55e" : "#E2E8F0",
                  fontSize: "13px",
                  fontFamily: code === "ar" ? "'IBM Plex Sans Arabic', sans-serif" : "var(--font-heading)",
                  fontWeight: isActive ? 700 : 500,
                  cursor: "pointer",
                  textAlign: isRtl ? "right" : "left",
                  transition: "all 0.15s ease",
                  width: "100%",
                }}
                onMouseEnter={(e) => {
                  if (!isActive) {
                    e.currentTarget.style.background = "rgba(255, 255, 255, 0.06)";
                    e.currentTarget.style.color = "#FFFFFF";
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isActive) {
                    e.currentTarget.style.background = "transparent";
                    e.currentTarget.style.color = "#E2E8F0";
                  }
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span>{item.flag}</span>
                  <span>{item.nativeName}</span>
                </div>
                {isActive && <Check size={14} style={{ color: "#22c55e" }} />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

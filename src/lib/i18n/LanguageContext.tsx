"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import type { Locale, TextDirection, Translations, LocaleMeta } from "./types";
import { SUPPORTED_LOCALES } from "./types";
import { en } from "./dictionaries/en";
import { ar } from "./dictionaries/ar";
import { fr } from "./dictionaries/fr";

const DICTIONARIES: Record<Locale, Translations> = {
  en,
  ar,
  fr,
};

interface LanguageContextValue {
  locale: Locale;
  setLocale: (newLocale: Locale) => void;
  t: Translations;
  dir: TextDirection;
  isRtl: boolean;
  isRTL: boolean;
  locales: Record<Locale, LocaleMeta>;
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

const STORAGE_KEY = "agriwise_locale";

export function LanguageProvider({
  children,
  defaultLocale = "en",
}: {
  children: React.ReactNode;
  defaultLocale?: Locale;
}) {
  const [locale, setLocaleState] = useState<Locale>(defaultLocale);
  const [mounted, setMounted] = useState(false);

  // Sync with document element on mount and when locale changes
  useEffect(() => {
    setMounted(true);
    const saved = localStorage.getItem(STORAGE_KEY) as Locale | null;
    if (saved && (saved === "en" || saved === "ar" || saved === "fr")) {
      setLocaleState(saved);
      document.documentElement.lang = saved;
      document.documentElement.dir = SUPPORTED_LOCALES[saved].dir;
    } else {
      document.documentElement.lang = defaultLocale;
      document.documentElement.dir = SUPPORTED_LOCALES[defaultLocale].dir;
    }
  }, [defaultLocale]);

  const setLocale = useCallback((newLocale: Locale) => {
    if (newLocale === "en" || newLocale === "ar" || newLocale === "fr") {
      setLocaleState(newLocale);
      try {
        localStorage.setItem(STORAGE_KEY, newLocale);
      } catch (e) {
        // localStorage might be unavailable in private browsing
      }
      if (typeof document !== "undefined") {
        document.documentElement.lang = newLocale;
        document.documentElement.dir = SUPPORTED_LOCALES[newLocale].dir;
      }
    }
  }, []);

  const dir: TextDirection = SUPPORTED_LOCALES[locale].dir;
  const isRtl = dir === "rtl";
  const t = DICTIONARIES[locale] || en;

  return (
    <LanguageContext.Provider
      value={{
        locale,
        setLocale,
        t,
        dir,
        isRtl,
        isRTL: isRtl,
        locales: SUPPORTED_LOCALES,
      }}
    >
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error("useLanguage must be used within a LanguageProvider");
  }
  return context;
}

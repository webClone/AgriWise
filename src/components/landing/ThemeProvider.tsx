"use client";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

type Theme = "dark" | "light";
const ThemeCtx = createContext<{ theme: Theme; toggle: () => void }>({ theme: "dark", toggle: () => {} });

export function useTheme() { return useContext(ThemeCtx); }

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>("dark");

  useEffect(() => {
    const saved = localStorage.getItem("ab-theme") as Theme | null;
    if (saved) setTheme(saved);
  }, []);

  const toggle = () => {
    setTheme(prev => {
      const next = prev === "dark" ? "light" : "dark";
      localStorage.setItem("ab-theme", next);
      return next;
    });
  };

  return <ThemeCtx.Provider value={{ theme, toggle }}>{children}</ThemeCtx.Provider>;
}

export function ThemeToggle() {
  const { theme, toggle } = useTheme();
  return (
    <button
      onClick={toggle}
      aria-label="Toggle theme"
      style={{
        width: "36px", height: "36px", borderRadius: "10px",
        background: theme === "dark" ? "rgba(71,85,105,0.15)" : "rgba(71,85,105,0.08)",
        border: "1px solid rgba(71,85,105,0.1)",
        display: "flex", alignItems: "center", justifyContent: "center",
        cursor: "pointer", transition: "all 0.25s ease",
        fontSize: "1rem",
      }}>
      {theme === "dark" ? "☀️" : "🌙"}
    </button>
  );
}

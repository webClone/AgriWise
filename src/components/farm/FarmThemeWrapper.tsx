"use client";
import { ThemeProvider, useTheme } from "@/components/landing/ThemeProvider";
import "@/components/landing/agribrain-theme.css";
import { type ReactNode } from "react";

function ThemeShell({ children }: { children: ReactNode }) {
  const { theme } = useTheme();
  return (
    <div data-theme={theme} style={{ minHeight: "100vh" }} suppressHydrationWarning={true}>
      {children}
    </div>
  );
}

export default function FarmThemeWrapper({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider>
      <ThemeShell>{children}</ThemeShell>
    </ThemeProvider>
  );
}

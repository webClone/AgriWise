"use client";
import Link from "next/link";
import { ThemeProvider, ThemeToggle, useTheme } from "@/components/landing/ThemeProvider";
import { ThemeLogo } from "@/components/landing/ThemeLogo";
import "@/components/landing/agribrain-theme.css";

export function NavbarContent({ activePage = "farm" }: { activePage?: string }) {
  const { theme } = useTheme();
  const linkStyle = (page: string) => ({
    fontSize: "13px",
    color: page === activePage ? "#4ade80" : "#94a3b8",
    textDecoration: "none" as const,
    fontWeight: page === activePage ? 700 : 500,
    transition: "color 0.15s",
  });

  return (
    <nav style={{
      position: "fixed", top: 0, left: 0, right: 0, zIndex: 100,
      padding: "10px 24px",
      background: theme === "dark" ? "rgba(5,10,20,0.82)" : "rgba(255,255,255,0.88)",
      backdropFilter: "blur(20px)", WebkitBackdropFilter: "blur(20px)",
      borderBottom: `1px solid ${theme === "dark" ? "rgba(71,85,105,0.06)" : "rgba(203,213,225,0.4)"}`,
    }} suppressHydrationWarning={true}>
      <div style={{ maxWidth: "1200px", margin: "0 auto", display: "flex", justifyContent: "space-between", alignItems: "center" }} suppressHydrationWarning={true}>
        <Link href="/" style={{ textDecoration: "none", display: "flex", alignItems: "center" }}>
          <ThemeLogo height={50} />
        </Link>
        <div style={{ display: "flex", alignItems: "center", gap: "20px" }} suppressHydrationWarning={true}>
          <Link href="/" style={linkStyle("home")}>Home</Link>
          <Link href="/farm" style={linkStyle("farm")}>My Farms</Link>
          <Link href="/agribrain" style={{ fontSize: "13px", color: "#818cf8", textDecoration: "none", fontWeight: 600, transition: "color 0.15s" }}>🧠 AgriBrain</Link>
          <ThemeToggle />
          <Link href="/farm/new" className="hp-cta-nav" style={{
            padding: "8px 20px", borderRadius: "10px",
            background: "linear-gradient(135deg,#22c55e,#16a34a)", color: "#fff",
            fontSize: "13px", fontWeight: 700, textDecoration: "none",
            boxShadow: "0 2px 12px rgba(34,197,94,0.2)",
          }}>+ New Farm</Link>
        </div>
      </div>
      <style>{`
        .hp-cta-nav { transition: all 0.15s ease; }
        .hp-cta-nav:hover { transform:translateY(-1px); box-shadow:0 4px 16px rgba(34,197,94,0.3) !important; }
      `}</style>
    </nav>
  );
}

export default function SharedNavbar({ activePage = "farm" }: { activePage?: string }) {
  return (
    <ThemeProvider>
      <NavbarContent activePage={activePage} />
    </ThemeProvider>
  );
}

"use client";
import { useState, useCallback } from "react";
import Link from "next/link";
import Image from "next/image";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";

/* ═══ HomeNav ══════════════════════════════════════════════════
   Redesigned marketing navigation.
   - Logo left
   - Links: Platform · Intelligence · Solutions · Science
   - Right: "Analyze My Field →" primary CTA + "For Organizations"
   - Frosted glass on dark background
   - Accessible mobile menu with focus trapping
   ═══════════════════════════════════════════════════════════════ */

const NAV_LINKS = [
  { label: "Platform", href: "#scale" },
  { label: "Intelligence", href: "#agribrain-organism" },
  { label: "Solutions", href: "#command-center" },
  { label: "Science", href: "/agribrain" },
] as const;

export default function HomeNav() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const prefersReduced = useReducedMotion();

  const toggleMobile = useCallback(() => {
    setMobileOpen((prev) => !prev);
  }, []);

  const closeMobile = useCallback(() => {
    setMobileOpen(false);
  }, []);

  return (
    <nav className="marketing-nav" role="navigation" aria-label="Main navigation">
      <div className="marketing-nav__inner">
        {/* Logo */}
        <Link href="/" aria-label="AgriWise home" style={{ textDecoration: "none", display: "flex", alignItems: "center" }}>
          <Image
            src="/logo-dark.png"
            alt="AgriWise"
            width={120}
            height={40}
            style={{ height: "36px", width: "auto" }}
            priority
          />
        </Link>

        {/* Desktop links */}
        <div className={`marketing-nav__links ${mobileOpen ? "marketing-nav__links--open" : ""}`}>
          {NAV_LINKS.map((link) => (
            <Link
              key={link.label}
              href={link.href}
              className="marketing-nav__link"
              onClick={closeMobile}
            >
              {link.label}
            </Link>
          ))}
          <Link
            href="/agribrain"
            className="marketing-nav__link"
            style={{ color: "var(--agribrain-violet)", fontWeight: 600 }}
            onClick={closeMobile}
          >
            AgriBrain
          </Link>

          {/* Mobile-only CTAs */}
          <div className="marketing-nav__mobile-ctas">
            <Link href="/farm/new" className="marketing-cta-primary" onClick={closeMobile}>
              Analyze My Field
            </Link>
          </div>
        </div>

        {/* Desktop right side */}
        <div className="marketing-nav__right">
          <Link href="#solutions" className="marketing-nav__link" style={{ fontSize: "12px" }}>
            For Organizations
          </Link>
          <Link href="/farm/new" className="marketing-cta-primary" style={{ padding: "8px 20px", fontSize: "13px", borderRadius: "10px" }}>
            Analyze My Field →
          </Link>
        </div>

        {/* Mobile toggle */}
        <button
          className="marketing-nav__mobile-toggle"
          onClick={toggleMobile}
          aria-expanded={mobileOpen}
          aria-controls="mobile-nav"
          aria-label={mobileOpen ? "Close navigation menu" : "Open navigation menu"}
        >
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
            {mobileOpen ? (
              <>
                <line x1="4" y1="4" x2="16" y2="16" />
                <line x1="16" y1="4" x2="4" y2="16" />
              </>
            ) : (
              <>
                <line x1="3" y1="5" x2="17" y2="5" />
                <line x1="3" y1="10" x2="17" y2="10" />
                <line x1="3" y1="15" x2="17" y2="15" />
              </>
            )}
          </svg>
        </button>
      </div>

      {/* Inline styles for desktop right side — these are nav-specific layout overrides */}
      <style>{`
        .marketing-nav__right {
          display: flex;
          align-items: center;
          gap: 16px;
        }
        .marketing-nav__mobile-ctas {
          display: none;
        }
        @media (max-width: 768px) {
          .marketing-nav__right {
            display: none;
          }
          .marketing-nav__mobile-ctas {
            display: flex;
            flex-direction: column;
            gap: 8px;
            padding-top: 8px;
            border-top: 1px solid var(--border-subtle);
          }
        }
      `}</style>
    </nav>
  );
}

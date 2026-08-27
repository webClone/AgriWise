import Link from "next/link";

/* ═══ MarketingFooter ══════════════════════════════════════════
   Redesigned footer for the marketing homepage.
   No fake product links. Real links only.
   ═══════════════════════════════════════════════════════════════ */

const FOOTER_SECTIONS = [
  {
    title: "Platform",
    links: [
      { label: "Field Monitoring", href: "/farm" },
      { label: "Crop Intelligence", href: "/farm" },
      { label: "AgriBrain", href: "/agribrain" },
    ],
  },
  {
    title: "Solutions",
    links: [
      { label: "Farmers", href: "#solutions" },
      { label: "Agronomists", href: "#solutions" },
      { label: "Farm Enterprise", href: "#solutions" },
      { label: "Banks & Insurance", href: "#solutions" },
      { label: "Government", href: "#solutions" },
    ],
  },
  {
    title: "Company",
    links: [
      { label: "About", href: "#" },
      { label: "Contact", href: "#" },
      { label: "Privacy", href: "#" },
      { label: "Terms", href: "#" },
    ],
  },
] as const;

export default function MarketingFooter() {
  return (
    <footer style={{
      borderTop: "1px solid var(--border-subtle)",
      padding: "56px 0 32px",
    }}>
      <div className="marketing-container">
        <div style={{
          display: "grid",
          gridTemplateColumns: "2fr 1fr 1fr 1fr",
          gap: "40px",
          marginBottom: "40px",
        }}>
          {/* Brand */}
          <div>
            <div style={{
              fontSize: "18px",
              fontWeight: 800,
              color: "var(--text-primary)",
              marginBottom: "12px",
            }}>
              Agri<span style={{ color: "var(--field-green)" }}>Wise</span>
            </div>
            <p style={{
              fontSize: "13px",
              color: "var(--text-dim)",
              lineHeight: 1.6,
              maxWidth: "300px",
            }}>
              Agricultural intelligence infrastructure.
              Powered by AgriBrain. Built in Algeria.
            </p>
          </div>

          {/* Link columns */}
          {FOOTER_SECTIONS.map((section) => (
            <div key={section.title}>
              <h4 style={{
                fontSize: "11px",
                fontWeight: 700,
                color: "var(--text-secondary)",
                textTransform: "uppercase",
                letterSpacing: "0.1em",
                marginBottom: "14px",
              }}>
                {section.title}
              </h4>
              {section.links.map((link) => (
                <Link
                  key={link.label}
                  href={link.href}
                  style={{
                    display: "block",
                    fontSize: "13px",
                    color: "var(--text-dim)",
                    textDecoration: "none",
                    marginBottom: "8px",
                    transition: "color 0.15s ease",
                  }}
                >
                  {link.label}
                </Link>
              ))}
            </div>
          ))}
        </div>

        {/* Bottom bar */}
        <div style={{
          borderTop: "1px solid var(--border-subtle)",
          paddingTop: "20px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "12px",
        }}>
          <span style={{ fontSize: "11px", color: "var(--text-faint)" }}>
            🇩🇿 Built in Algeria · © {new Date().getFullYear()} AgriWise
          </span>
          <span style={{ fontSize: "11px", color: "var(--text-faint)" }}>
            Powered by AgriBrain · Copernicus Programme
          </span>
        </div>
      </div>
    </footer>
  );
}

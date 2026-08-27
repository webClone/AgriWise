
import { prisma } from "@/lib/prisma";
import SeedDemoButton from "@/components/farm/SeedDemoButton";
import { FarmHeroClient, FarmStatsClient, FarmCardClient } from "@/components/farm/FarmPageClient";
import FarmThemeWrapper from "@/components/farm/FarmThemeWrapper";
import { NavbarContent } from "@/components/landing/SharedNavbar";
import Link from "next/link";
import { getSession } from "@/lib/session";
import DevelopmentSessionBootstrap from "@/components/auth/DevelopmentSessionBootstrap";
import { ObjectId } from "bson";

export const dynamic = "force-dynamic";

async function getFarms() {
  try {
    const session = await getSession();
    const sessionUserId = session?.userId;
    const farms = sessionUserId && ObjectId.isValid(sessionUserId)
      ? await prisma.farm.findMany({
          where: { userId: sessionUserId },
          include: { plots: { include: { cropCycles: true } } },
          orderBy: { createdAt: "desc" },
        })
      : [];

    if (farms.length > 0 || process.env.NODE_ENV !== "development") {
      return { farms, bootstrapFarmId: null as string | null };
    }

    // Signed local cookies can outlive a reseeded user. Repair only an absent
    // identity; a real owner with zero farms keeps the genuine empty state.
    const sessionUserExists = sessionUserId && ObjectId.isValid(sessionUserId)
      ? await prisma.user.findUnique({
          where: { id: sessionUserId },
          select: { id: true },
        })
      : null;
    if (sessionUserExists) {
      return { farms, bootstrapFarmId: null as string | null };
    }

    const existingFarm = await prisma.farm.findFirst({
      orderBy: { createdAt: "desc" },
      select: { id: true },
    });
    return { farms, bootstrapFarmId: existingFarm?.id || null };
  } catch (error) {
    console.error("Error fetching farms:", error);
    return { farms: [], bootstrapFarmId: null as string | null };
  }
}

export default async function FarmPage() {
  const { farms, bootstrapFarmId } = await getFarms();
  if (bootstrapFarmId) {
    return <DevelopmentSessionBootstrap farmId={bootstrapFarmId} />;
  }
  const totalArea = farms.reduce((acc, f) => acc + f.totalArea, 0);
  const totalPlots = farms.reduce((acc, f) => acc + f.plots.length, 0);
  const totalCrops = farms.reduce((acc, f) => acc + f.plots.reduce((a2, p) => a2 + (p.cropCycles?.length || 0), 0), 0);

  const farmCards = farms.map(f => ({
    id: f.id, name: f.name, wilaya: f.wilaya, totalArea: f.totalArea,
    plots: f.plots.map(p => ({
      id: p.id, name: p.name, area: p.area,
      cropCycles: (p.cropCycles || []).map(c => ({ cropCode: c.cropCode, status: String(c.status) })),
    })),
  }));

  return (
    <FarmThemeWrapper>
    <main style={{ minHeight: "100vh", background: "#060a13", color: "#e2e8f0", fontFamily: "'Inter', system-ui, sans-serif", position: "relative", overflow: "hidden" }}>
      <NavbarContent activePage="farm" />
      {/* Ambient background mesh */}
      <div style={{ position: "fixed", inset: 0, pointerEvents: "none", zIndex: 0 }}>
        <div style={{ position: "absolute", top: "-20%", left: "-10%", width: "55%", height: "65%", background: "radial-gradient(ellipse, rgba(34,197,94,0.04) 0%, transparent 65%)" }} />
        <div style={{ position: "absolute", bottom: "-15%", right: "-10%", width: "50%", height: "55%", background: "radial-gradient(ellipse, rgba(59,130,246,0.03) 0%, transparent 65%)" }} />
        <div style={{ position: "absolute", top: "40%", left: "30%", width: "40%", height: "40%", background: "radial-gradient(ellipse, rgba(168,85,247,0.02) 0%, transparent 65%)" }} />
      </div>

      <div style={{ position: "relative", zIndex: 1, paddingTop: "70px" }}>
        <FarmHeroClient farmCount={farms.length} />
        <FarmStatsClient farms={farms.length} totalPlots={totalPlots} totalArea={totalArea} totalCrops={totalCrops} />

        {/* ── Farms Grid ──────────────────────────────────────────── */}
        <div style={{ maxWidth: "1100px", margin: "0 auto", padding: "0 24px 100px" }}>
          {farms.length === 0 ? (
            <div className="fm-anim" style={{
              textAlign: "center", padding: "80px 24px", borderRadius: "20px",
              border: "1px dashed rgba(71,85,105,0.15)", background: "rgba(15,23,42,0.2)",
              animationDelay: "0.25s",
            }}>
              <div style={{ fontSize: "4rem", marginBottom: "16px", filter: "grayscale(0.2)" }}>🚜</div>
              <h3 style={{ fontSize: "1.3rem", fontWeight: 600, color: "#e2e8f0", marginBottom: "8px" }}>No farms yet</h3>
              <p style={{ fontSize: "14px", color: "#64748b", maxWidth: "380px", margin: "0 auto 28px", lineHeight: 1.6 }}>
                Add your first farm to unlock satellite-powered crop intelligence and yield forecasting.
              </p>
              <div style={{ display: "flex", gap: "12px", justifyContent: "center", flexWrap: "wrap" }}>
                <Link href="/farm/new" style={{ padding: "12px 24px", borderRadius: "12px", background: "linear-gradient(135deg, #22c55e, #16a34a)", color: "#fff", fontSize: "14px", fontWeight: 600, textDecoration: "none", boxShadow: "0 4px 20px rgba(34,197,94,0.25)" }}>+ Add New Farm</Link>
                <SeedDemoButton />
              </div>
            </div>
          ) : (
            <>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "16px" }} className="fm-anim" >
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <div style={{ width: "3px", height: "16px", borderRadius: "2px", background: "linear-gradient(180deg, #4ade80, #22d3ee)" }} />
                  <span style={{ fontSize: "12px", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.1em" }}>All Farms</span>
                  <span style={{ fontSize: "10px", padding: "2px 8px", borderRadius: "6px", background: "rgba(71,85,105,0.1)", color: "#64748b", fontWeight: 600 }}>{farms.length}</span>
                </div>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(380px, 1fr))", gap: "16px" }}>
                {farmCards.map((farm, idx) => (
                  <FarmCardClient key={farm.id} farm={farm} idx={idx} />
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {/* ── Premium Animation System ──────────────────────────── */}
      <style>{`
        @keyframes farmSlideUp {
          from { opacity: 0; transform: translateY(24px) scale(0.98); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }
        .fm-anim {
          opacity: 0;
          animation: farmSlideUp 0.7s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }
        .fm-gradient-text {
          background: linear-gradient(135deg, #4ade80 0%, #22d3ee 40%, #818cf8 100%);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-size: 200% 200%;
          animation: gradientShift 6s ease infinite;
        }
        @keyframes gradientShift {
          0%, 100% { background-position: 0% 50%; }
          50% { background-position: 100% 50%; }
        }
        .fm-logo-pulse { position: relative; }
        .fm-logo-ring {
          position: absolute; inset: -3px; border-radius: 16px;
          border: 1px solid rgba(34,197,94,0.2);
          animation: logoRing 3s ease-in-out infinite;
        }
        @keyframes logoRing {
          0%, 100% { opacity: 0.3; transform: scale(1); }
          50% { opacity: 0.6; transform: scale(1.08); }
        }
        .fm-stat-card { transition: all 0.25s cubic-bezier(0.16,1,0.3,1); }
        .fm-stat-card:hover {
          border-color: rgba(100,116,139,0.2);
          transform: translateY(-3px);
          box-shadow: 0 8px 30px rgba(0,0,0,0.2);
        }
        .fm-farm-card { transition: all 0.3s cubic-bezier(0.16,1,0.3,1); }
        .fm-farm-card:hover {
          border-color: rgba(34,197,94,0.18) !important;
          background: rgba(15,23,42,0.65) !important;
          transform: translateY(-4px) scale(1.005);
          box-shadow: 0 16px 50px rgba(0,0,0,0.35), 0 0 80px rgba(34,197,94,0.04);
        }
        .fm-farm-card:hover .fm-card-arrow { opacity: 1; transform: translateY(-50%) translateX(0); }
        .fm-farm-card:hover .fm-farm-icon { transform: scale(1.08); box-shadow: 0 0 24px rgba(34,197,94,0.12); }
        .fm-farm-icon { transition: all 0.3s cubic-bezier(0.16,1,0.3,1); }
        .fm-card-gradient {
          background: linear-gradient(90deg, #22c55e, #3b82f6, #8b5cf6, transparent);
          background-size: 200% 100%;
          animation: gradientSlide 4s ease infinite;
        }
        @keyframes gradientSlide {
          0% { background-position: 100% 0; }
          100% { background-position: -100% 0; }
        }
        .fm-card-arrow {
          position: absolute; right: 18px; top: 50%; transform: translateY(-50%) translateX(8px);
          opacity: 0; transition: all 0.25s ease; color: #4ade80;
        }
        .fm-usage-bar { transition: width 1.2s cubic-bezier(0.16,1,0.3,1) 0.4s; }
        .fm-badge {
          font-size: 10px; padding: 4px 10px; border-radius: 8px; font-weight: 700;
          border: 1px solid; white-space: nowrap;
        }
        .fm-chip {
          font-size: 10px; padding: 3px 10px; border-radius: 6px;
          background: rgba(71,85,105,0.1); border: 1px solid rgba(71,85,105,0.08);
          color: #94a3b8; font-weight: 500;
        }
        .fm-add-btn {
          transition: all 0.2s cubic-bezier(0.16,1,0.3,1);
          position: relative; overflow: hidden;
        }
        .fm-add-btn:hover {
          transform: translateY(-2px) scale(1.02);
          box-shadow: 0 8px 32px rgba(34,197,94,0.4), inset 0 1px 0 rgba(255,255,255,0.2) !important;
        }
        .fm-add-btn:active { transform: translateY(0) scale(0.97); }
        .fm-btn-shimmer {
          position: absolute; top: 0; left: -100%; width: 100%; height: 100%;
          background: linear-gradient(90deg, transparent, rgba(255,255,255,0.15), transparent);
          animation: shimmer 3s ease-in-out infinite;
        }
        @keyframes shimmer {
          0% { left: -100%; }
          40%, 100% { left: 100%; }
        }
        /* ── Farm light mode overrides ──────────────────────── */
        [data-theme="light"] main {
          background: #f8fafc !important;
          color: #1e293b !important;
        }
        [data-theme="light"] .fm-farm-card {
          background: rgba(255,255,255,0.85) !important;
          border-color: rgba(203,213,225,0.35) !important;
        }
        [data-theme="light"] .fm-farm-card:hover {
          background: rgba(255,255,255,0.95) !important;
          border-color: rgba(34,197,94,0.25) !important;
          box-shadow: 0 8px 30px rgba(0,0,0,0.08) !important;
        }
        [data-theme="light"] .fm-stat-card {
          background: rgba(255,255,255,0.85) !important;
          border-color: rgba(203,213,225,0.35) !important;
        }
        [data-theme="light"] .fm-stat-card:hover {
          box-shadow: 0 4px 20px rgba(0,0,0,0.06) !important;
        }
        [data-theme="light"] .fm-chip {
          background: rgba(241,245,249,0.8) !important;
          border-color: rgba(203,213,225,0.4) !important;
          color: #475569 !important;
        }
        [data-theme="light"] .fm-badge {
          background: rgba(241,245,249,0.6) !important;
        }
        [data-theme="light"] h1 {
          color: #1e293b !important;
        }
        [data-theme="light"] .fm-gradient-text {
          -webkit-text-fill-color: transparent !important;
        }
        @media (max-width: 640px) {
          .fm-stat-card { min-width: 140px; }
        }
      `}</style>
    </main>
    </FarmThemeWrapper>
  );
}

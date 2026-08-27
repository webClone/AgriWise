
import { prisma } from "@/lib/prisma";
import { notFound } from "next/navigation";
import FarmMapClient from "@/components/farm/FarmMapClient";
import PlotsSection from "@/components/farm/PlotsSection";
import FarmHeaderActions from "@/components/farm/FarmHeaderActions";
import EquipmentList from "@/components/farm/EquipmentList";
import { FarmDetailHero } from "@/components/farm/FarmDetailClient";
import FarmThemeWrapper from "@/components/farm/FarmThemeWrapper";
import { NavbarContent } from "@/components/landing/SharedNavbar";
import { getSession } from "@/lib/session";
import DevelopmentSessionBootstrap from "@/components/auth/DevelopmentSessionBootstrap";
import { ObjectId } from "bson";

async function getFarmContext(id: string) {
  try {
    const session = await getSession();
    if (!session?.userId) return null;

    const farm = await prisma.farm.findFirst({
      where: {
        id,
        userId: session.userId,
      },
      include: {
        plots: { include: { cropCycles: true } },
        equipment: { orderBy: { id: "desc" } },
      },
    });
    if (!farm) return null;

    const farmView = {
      id: farm.id, name: farm.name,
      nameAr: farm.nameAr || null,
      wilaya: farm.wilaya, commune: farm.commune || null,
      totalArea: farm.totalArea,
      latitude: farm.latitude || null, longitude: farm.longitude || null,
      soilType: farm.soilType || null, waterSource: farm.waterSource || null,
      irrigationType: farm.irrigationType || null,
    };
    const plots = farm.plots.map(p => ({
      id: p.id, name: p.name,
      nameAr: p.nameAr || undefined,
      area: p.area,
      soilType: p.soilType ? String(p.soilType) : undefined,
      irrigation: p.irrigation ? String(p.irrigation) : undefined,
      geoJson: p.geoJson,
    }));
    const equipment = farm.equipment.map(e => ({
      id: e.id, name: e.name, type: e.type,
      condition: e.condition, quantity: e.quantity,
    }));
    const cropCycles = farm.plots.flatMap(p => p.cropCycles.map(c => ({
      id: c.id, cropCode: c.cropCode,
      cropNameAr: c.cropNameAr || undefined,
      variety: c.variety || undefined, status: String(c.status),
      estimatedYield: c.estimatedYield ?? undefined, plotId: c.plotId,
    })));

    return { farm: farmView, plots, equipment, cropCycles };
  } catch (error) {
    console.error("getFarmContext error:", error);
    return null;
  }
}

export default async function FarmDetailsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const context = await getFarmContext(id);
  if (!context) {
    if (process.env.NODE_ENV === "development" && ObjectId.isValid(id)) {
      try {
        const requestedFarm = await prisma.farm.findUnique({
          where: { id },
          select: { id: true },
        });
        if (requestedFarm) return <DevelopmentSessionBootstrap farmId={id} />;
      } catch (dbErr) {
        console.error("Development bootstrap Prisma query error:", dbErr);
      }
    }
    notFound();
  }

  const { farm, plots, equipment, cropCycles } = context;
  const activeCrops = cropCycles.filter(c => c.status === "ACTIVE" || c.status === "GROWING").length;
  const mappedArea = plots.reduce((a, p) => a + p.area, 0);

  return (
    <FarmThemeWrapper>
    <main style={{ minHeight: "100vh", background: "#060a13", color: "#e2e8f0", fontFamily: "'Inter', system-ui, sans-serif", position: "relative", overflow: "hidden" }}>
      <NavbarContent activePage="farm" />
      {/* Ambient mesh */}
      <div style={{ position: "fixed", inset: 0, pointerEvents: "none", zIndex: 0 }} suppressHydrationWarning={true}>
        <div style={{ position: "absolute", top: "-20%", right: "-15%", width: "50%", height: "55%", background: "radial-gradient(ellipse, rgba(34,197,94,0.03) 0%, transparent 65%)" }} suppressHydrationWarning={true} />
        <div style={{ position: "absolute", bottom: "-10%", left: "-10%", width: "45%", height: "45%", background: "radial-gradient(ellipse, rgba(59,130,246,0.025) 0%, transparent 65%)" }} suppressHydrationWarning={true} />
      </div>

      <div style={{ position: "relative", zIndex: 1, paddingTop: "70px" }} suppressHydrationWarning={true}>
        {/* Actions float */}
        <div style={{ position: "absolute", top: "44px", right: "24px", zIndex: 10, maxWidth: "1100px" }} suppressHydrationWarning={true}>
          <FarmHeaderActions farm={farm} />
        </div>

        {/* Hero + Stats + Properties (client) */}
        <FarmDetailHero
          farm={farm}
          plotCount={plots.length}
          activeCrops={activeCrops}
          equipmentCount={equipment.length}
          mappedArea={mappedArea}
        />

        {/* ── Map ────────────────────────────────────────────── */}
        <div className="fd-anim" style={{ maxWidth: "1100px", margin: "0 auto", padding: "0 24px 24px", animationDelay: "0.3s" }} suppressHydrationWarning={true}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }} suppressHydrationWarning={true}>
            <div style={{ width: "3px", height: "14px", borderRadius: "2px", background: "linear-gradient(180deg, #4ade80, #22d3ee)" }} suppressHydrationWarning={true} />
            <span style={{ fontSize: "11px", fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.1em" }}>Farm Location</span>
            {plots.length > 0 && <span style={{ fontSize: "9px", padding: "2px 8px", borderRadius: "5px", background: "rgba(34,197,94,0.06)", color: "#4ade80", fontWeight: 600 }}>{plots.length} plots mapped</span>}
          </div>
          <div style={{ borderRadius: "18px", overflow: "hidden", border: "1px solid rgba(71,85,105,0.1)", background: "rgba(15,23,42,0.35)", position: "relative" }} suppressHydrationWarning={true}>
            <div style={{ position: "absolute", top: "14px", right: "14px", zIndex: 10, display: "flex", gap: "6px" }} suppressHydrationWarning={true}>
              {farm.latitude && farm.longitude && (
                <span style={{ fontSize: "9px", color: "#475569", fontFamily: "monospace", padding: "4px 10px", borderRadius: "6px", background: "rgba(8,12,25,0.8)", backdropFilter: "blur(8px)", border: "1px solid rgba(71,85,105,0.1)" }}>
                  📍 {farm.latitude.toFixed(4)}° {farm.longitude.toFixed(4)}°
                </span>
              )}
            </div>
            <div style={{ height: "320px" }} suppressHydrationWarning={true}>
              {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
              <FarmMapClient farms={[farm] as any} plots={plots as any} />
            </div>
          </div>
        </div>

        {/* ── Plots ──────────────────────────────────────────── */}
        <div className="fd-anim" style={{ maxWidth: "1100px", margin: "0 auto", padding: "0 24px", animationDelay: "0.35s" }} suppressHydrationWarning={true}>
          <PlotsSection
            farmId={id}
            plots={plots as { id: string; name: string; nameAr?: string; area: number; soilType?: string; irrigation?: string }[]}
            cropCycles={cropCycles as { id: string; cropCode: string; cropNameAr?: string; variety?: string; status: string; plotId: string }[]}
            farmCoordinates={farm.latitude && farm.longitude ? { lat: farm.latitude, lng: farm.longitude } : undefined}
          />
        </div>

        {/* ── Equipment ──────────────────────────────────────── */}
        <div className="fd-anim" style={{ maxWidth: "1100px", margin: "0 auto", padding: "0 24px 100px", animationDelay: "0.4s" }} suppressHydrationWarning={true}>
          <EquipmentList equipment={equipment} farmId={id} />
        </div>
      </div>

      {/* ── Animation System ─────────────────────────────────── */}
      <style>{`
        @keyframes fdSlideUp {
          from { opacity: 0; transform: translateY(24px) scale(0.98); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }
        .fd-anim {
          opacity: 0;
          animation: fdSlideUp 0.7s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }
        .fd-live-dot {
          width: 6px; height: 6px; border-radius: 50%;
          background: #22c55e; box-shadow: 0 0 8px #22c55e80;
          animation: livePulse 2s ease-in-out infinite;
        }
        @keyframes livePulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.5; transform: scale(1.4); }
        }
        .fd-stat { transition: all 0.25s cubic-bezier(0.16,1,0.3,1); }
        .fd-stat:hover {
          border-color: rgba(100,116,139,0.2);
          transform: translateY(-3px);
          box-shadow: 0 8px 30px rgba(0,0,0,0.2);
        }
        .fd-info { transition: all 0.25s cubic-bezier(0.16,1,0.3,1); }
        .fd-info:hover {
          border-color: rgba(100,116,139,0.18);
          transform: translateY(-2px);
          background: rgba(15,23,42,0.55) !important;
        }
        .fd-bar { transition: width 1.2s cubic-bezier(0.16,1,0.3,1) 0.6s; }
        .fd-back-btn { transition: all 0.2s ease; }
        .fd-back-btn:hover {
          background: rgba(71,85,105,0.2) !important;
          border-color: rgba(71,85,105,0.25) !important;
          color: #e2e8f0 !important;
          transform: translateX(-3px);
        }
        /* ── Farm Detail light mode ─────────────────────────── */
        [data-theme="light"] main {
          background: #f8fafc !important;
          color: #1e293b !important;
        }
        [data-theme="light"] .fd-stat {
          background: rgba(255,255,255,0.85) !important;
          border-color: rgba(203,213,225,0.35) !important;
        }
        [data-theme="light"] .fd-stat:hover {
          box-shadow: 0 4px 20px rgba(0,0,0,0.06) !important;
        }
        [data-theme="light"] .fd-info {
          background: rgba(255,255,255,0.8) !important;
          border-color: rgba(203,213,225,0.35) !important;
        }
        [data-theme="light"] .fd-info:hover {
          background: rgba(255,255,255,0.95) !important;
        }
        [data-theme="light"] .fd-back-btn {
          background: rgba(241,245,249,0.8) !important;
          border-color: rgba(203,213,225,0.4) !important;
          color: #475569 !important;
        }
        [data-theme="light"] .fd-back-btn:hover {
          background: rgba(226,232,240,0.8) !important;
          color: #1e293b !important;
        }
        [data-theme="light"] h1, [data-theme="light"] h2, [data-theme="light"] h3 {
          color: #1e293b !important;
        }
      `}</style>
    </main>
    </FarmThemeWrapper>
  );
}

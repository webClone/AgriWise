
import { prisma } from "@/lib/prisma";
import { notFound } from "next/navigation";
import Link from "next/link";
import FarmMapClient from "@/components/farm/FarmMapClient";
import PlotsSection from "@/components/farm/PlotsSection";
import FarmHeaderActions from "@/components/farm/FarmHeaderActions";
import EquipmentList from "@/components/farm/EquipmentList";

async function getFarm(id: string) {
  try {
    const farm = await prisma.farm.findUnique({ where: { id } });
    if (!farm) return null;
    
    return {
      id: farm.id,
      name: farm.name,
      nameAr: (farm as Record<string, unknown>).nameAr as string || null,
      wilaya: farm.wilaya,
      commune: farm.commune || null,
      totalArea: farm.totalArea,
      latitude: farm.latitude || null,
      longitude: farm.longitude || null,
      soilType: farm.soilType || null,
      waterSource: farm.waterSource || null,
      irrigationType: farm.irrigationType || null,
    };
  } catch (error) {
    console.error("getFarm error:", error);
    return null;
  }
}

async function getPlots(farmId: string) {
  try {
    const plots = await prisma.plot.findMany({ where: { farmId } });
    
    return plots.map(p => ({
      id: p.id,
      name: p.name,
      nameAr: (p as Record<string, unknown>).nameAr as string | undefined,
      area: p.area,
      soilType: p.soilType ? String(p.soilType) : undefined,
      irrigation: p.irrigation ? String(p.irrigation) : undefined,
      geoJson: (p as Record<string, unknown>).geoJson,
    }));
  } catch (error) {
    console.error("getPlots error:", error);
    return [];
  }
}

async function getEquipment(farmId: string) {
  try {
    const equipment = await prisma.equipment.findMany({
      where: { farmId },
      orderBy: { id: 'desc' } // persistent ordering
    });
    
    return equipment.map(e => ({
      id: e.id,
      name: e.name,
      type: e.type,
      condition: e.condition,
      quantity: e.quantity,
    }));
  } catch (error) {
    console.error("getEquipment error:", error);
    return [];
  }
}

async function getCropCycles(plotIds: string[]) {
  try {
    if (plotIds.length === 0) return [];
    
    const cycles = await prisma.cropCycle.findMany({
      where: { plotId: { in: plotIds } }
    });
    
    return cycles.map(c => ({
      id: c.id,
      cropCode: c.cropCode,
      cropNameAr: (c as Record<string, unknown>).cropNameAr as string | undefined,
      variety: c.variety || undefined,
      status: String(c.status),
      estimatedYield: c.estimatedYield ?? undefined,
      plotId: c.plotId,
    }));
  } catch (error) {
    console.error("getCropCycles error:", error);
    return [];
  }
}


const HomeIcon = () => (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12l8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75M8.25 21h8.25" />
    </svg>
  );
  const FarmIcon = () => (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v2.25m6.364.386l-1.591 1.591M21 12h-2.25m-.386 6.364l-1.591-1.591M12 18.75V21m-4.773-4.227l-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z" />
    </svg>
  );
  const CalendarIcon = () => (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
    </svg>
  );
  const WeatherIcon = () => (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15a4.5 4.5 0 004.5 4.5H18a3.75 3.75 0 001.332-7.257 3 3 0 00-3.758-3.848 5.25 5.25 0 00-10.233 2.33A4.502 4.502 0 002.25 15z" />
    </svg>
  );
  const UserIcon = () => (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
    </svg>
  );

export default async function FarmDetailsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const farm = await getFarm(id);

  if (!farm) {
    notFound(); 
  }

  // Fetch related data
  const plots = await getPlots(id);
  const equipment = await getEquipment(id);
  const cropCycles = await getCropCycles(plots.map(p => p.id));

  // Icons for bottom nav
  // Icons are defined outside the component to avoid re-creation on render

  return (
    <main className="page" style={{ paddingBottom: "100px" }}>
      {/* Header with back button */}
      <header className="page-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <Link 
            href="/farm" 
            style={{ 
              width: "40px", 
              height: "40px", 
              display: "flex", 
              alignItems: "center", 
              justifyContent: "center",
              borderRadius: "12px",
              background: "var(--background-tertiary)",
              color: "var(--foreground-muted)"
            }}
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" style={{ width: "20px", height: "20px" }}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
            </svg>
          </Link>
          <div>
            <h1 className="page-title" style={{ marginBottom: "0.25rem" }}>{farm.name}</h1>
            <p className="page-subtitle" style={{ margin: 0 }}>
              📍 {farm.commune && `${farm.commune}، `}{farm.wilaya} • <span style={{ color: "var(--color-primary-500)" }}>{farm.totalArea} هكتار</span>
            </p>
          </div>
        </div>
        <FarmHeaderActions farm={farm} />
      </header>

      {/* Stats Grid */}
      <div className="stats-grid fade-in" style={{ marginBottom: "1.5rem" }}>
        <div className="stat-card">
          <div className="stat-value">{farm.totalArea}</div>
          <div className="stat-label">هكتار</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{plots.length}</div>
          <div className="stat-label">قطع</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{cropCycles.length}</div>
          <div className="stat-label">محاصيل</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{equipment.length}</div>
          <div className="stat-label">معدات</div>
        </div>
      </div>

      {/* Farm Info Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem", marginBottom: "1.5rem" }}>
        <div className="card" style={{ padding: "1rem", textAlign: "center" }}>
          <div style={{ fontSize: "1.5rem", marginBottom: "0.25rem" }}>💧</div>
          <div style={{ fontWeight: 600, fontSize: "0.9rem" }}>{farm.irrigationType || "غير محدد"}</div>
          <div className="page-subtitle" style={{ margin: 0, fontSize: "0.75rem" }}>نظام الري</div>
        </div>
        <div className="card" style={{ padding: "1rem", textAlign: "center" }}>
          <div style={{ fontSize: "1.5rem", marginBottom: "0.25rem" }}>🪨</div>
          <div style={{ fontWeight: 600, fontSize: "0.9rem" }}>{farm.soilType || "غير محلل"}</div>
          <div className="page-subtitle" style={{ margin: 0, fontSize: "0.75rem" }}>نوع التربة</div>
        </div>
        <div className="card" style={{ padding: "1rem", textAlign: "center" }}>
          <div style={{ fontSize: "1.5rem", marginBottom: "0.25rem" }}>💦</div>
          <div style={{ fontWeight: 600, fontSize: "0.9rem" }}>{farm.waterSource || "غير محدد"}</div>
          <div className="page-subtitle" style={{ margin: 0, fontSize: "0.75rem" }}>مصدر المياه</div>
        </div>
        <div className="card" style={{ padding: "1rem", textAlign: "center" }}>
          <div style={{ fontSize: "1.5rem", marginBottom: "0.25rem" }}>📍</div>
          <div style={{ fontWeight: 600, fontSize: "0.9rem" }}>{farm.wilaya}</div>
          <div className="page-subtitle" style={{ margin: 0, fontSize: "0.75rem" }}>الولاية</div>
        </div>
      </div>

      {/* Map */}
      <div className="card fade-in" style={{ marginBottom: "1.5rem", padding: 0, overflow: "hidden" }}>
        <div style={{ padding: "1rem", borderBottom: "1px solid var(--background-tertiary)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontWeight: 600 }}>🗺️ موقع المزرعة</span>
          {farm.latitude && farm.longitude && (
            <span className="page-subtitle" style={{ margin: 0, fontSize: "0.75rem" }}>{farm.latitude.toFixed(3)}°, {farm.longitude.toFixed(3)}°</span>
          )}
        </div>
        <div style={{ height: "200px" }}>
          {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
          <FarmMapClient farms={[farm] as any} plots={plots as any} />
        </div>
      </div>





      {/* Plots Section */}
      <PlotsSection 
        farmId={id} 
        plots={plots as { id: string; name: string; nameAr?: string; area: number; soilType?: string; irrigation?: string }[]} 
        cropCycles={cropCycles as { id: string; cropCode: string; cropNameAr?: string; variety?: string; status: string; plotId: string }[]} 
        farmCoordinates={
          farm.latitude && farm.longitude 
            ? { lat: farm.latitude, lng: farm.longitude } 
            : undefined
        }
      />

      {/* Equipment Section */}
      <EquipmentList equipment={equipment} farmId={id} />

      {/* Bottom Navigation */}
      <nav className="nav-bottom">
        <Link href="/" className="nav-item"><HomeIcon /><span>الرئيسية</span></Link>
        <Link href="/farm" className="nav-item active"><FarmIcon /><span>المزارع</span></Link>
        <Link href="/calendar" className="nav-item"><CalendarIcon /><span>التقويم</span></Link>
        <Link href="/weather" className="nav-item"><WeatherIcon /><span>الطقس</span></Link>
        <Link href="/profile" className="nav-item"><UserIcon /><span>حسابي</span></Link>
      </nav>
    </main>
  );
}


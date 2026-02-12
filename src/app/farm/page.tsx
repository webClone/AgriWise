
import { prisma } from "@/lib/prisma";
import Link from "next/link";
import SeedDemoButton from "@/components/farm/SeedDemoButton";

// Icons
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

const PlusIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" style={{ width: "24px", height: "24px" }}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
  </svg>
);

async function getFarms() {
  try {
    return await prisma.farm.findMany({
      include: {
        plots: true
      },
      orderBy: { createdAt: 'desc' }
    });
  } catch (error) {
    console.error("Error fetching farms:", error);
    return [];
  }
}

export default async function FarmPage() {
  const farms = await getFarms();

  // Calculate simple stats
  const totalArea = farms.reduce((acc, f) => acc + f.totalArea, 0);
  const totalPlots = farms.reduce((acc, f) => acc + f.plots.length, 0);

  return (
    <main className="page" style={{ paddingBottom: "100px" }}>
      {/* Header */}
      <header className="page-header flex justify-between items-center">
        <div>
          <h1 className="page-title">مزارعي</h1>
          <p className="page-subtitle">إدارة المزارع والقطع الزراعية</p>
        </div>
        <Link 
          href="/farm/new" 
          className="bg-green-600 text-white px-4 py-2 rounded-lg flex items-center gap-2 hover:bg-green-700 transition"
        >
          <PlusIcon /> <span className="hidden md:inline">إضافة مزرعة</span>
        </Link>
      </header>

      {/* Stats Summary */}
      <div className="stats-grid fade-in" style={{ marginBottom: "1.5rem" }}>
        <div className="stat-card">
          <div className="stat-value">{farms.length}</div>
          <div className="stat-label">المزارع</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{totalPlots}</div>
          <div className="stat-label">القطع</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{Number(totalArea).toFixed(1)}</div>
          <div className="stat-label">هكتار</div>
        </div>
      </div>

      {/* Farms List */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {farms.length === 0 ? (
          <div className="col-span-full card text-center py-10" style={{ borderStyle: "dashed" }}>
             <div className="text-4xl mb-4">🚜</div>
             <h3 style={{ fontSize: "1.125rem", fontWeight: "bold", marginBottom: "0.5rem" }}>لا توجد مزارع بعد</h3>
             <p className="page-subtitle" style={{ marginBottom: "1.5rem" }}>ابدأ بإضافة مزرعتك الأولى للحصول على تحليلات ذكية.</p>
             <div style={{ display: "flex", gap: "1rem", justifyContent: "center", flexWrap: "wrap" }}>
               <Link href="/farm/new" className="btn btn-primary">
                 + إضافة مزرعة جديدة
               </Link>
               <SeedDemoButton />
             </div>
          </div>
        ) : (
          farms.map((farm) => (
            <Link key={farm.id} href={`/farm/${farm.id}`} className="block">
              <div className="card" style={{ position: "relative", overflow: "hidden" }}>
                <div style={{ 
                  position: "absolute", 
                  top: 0, 
                  right: 0, 
                  width: "4px", 
                  height: "100%", 
                  background: "var(--color-primary-500)", 
                  opacity: 0,
                  transition: "opacity 0.2s"
                }} className="group-hover-indicator" />
                
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "1rem" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                    <div style={{ 
                      width: "48px", 
                      height: "48px", 
                      background: "rgba(34, 197, 94, 0.1)", 
                      borderRadius: "50%", 
                      display: "flex", 
                      alignItems: "center", 
                      justifyContent: "center",
                      fontSize: "1.5rem"
                    }}>
                       🚜
                    </div>
                    <div>
                      <h3 style={{ fontWeight: "bold", fontSize: "1.125rem" }}>{farm.name}</h3>
                      <p className="page-subtitle" style={{ margin: 0 }}>{farm.wilaya} • {farm.totalArea} هكتار</p>
                    </div>
                  </div>
                  <span style={{ 
                    background: "var(--background-tertiary)", 
                    padding: "0.25rem 0.5rem", 
                    borderRadius: "0.25rem",
                    fontSize: "0.75rem"
                  }}>
                    {farm.plots.length} قطع
                  </span>
                </div>

                <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem", overflowX: "auto", paddingBottom: "0.5rem" }}>
                   {farm.plots.slice(0, 3).map(plot => (
                     <span key={plot.id} style={{ 
                       fontSize: "0.75rem", 
                       border: "1px solid var(--background-tertiary)", 
                       borderRadius: "0.25rem",
                       padding: "0.25rem 0.5rem",
                       background: "var(--background-tertiary)",
                       whiteSpace: "nowrap"
                     }}>
                       {plot.name} ({plot.area}ha)
                     </span>
                   ))}
                   {farm.plots.length > 3 && (
                     <span style={{ fontSize: "0.75rem", padding: "0.25rem 0.5rem", opacity: 0.6 }}>+ {farm.plots.length - 3}</span>
                   )}
                </div>
              </div>
            </Link>
          ))
        )}
      </div>

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

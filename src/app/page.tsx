"use client";

import Link from "next/link";
import { useState, useEffect } from "react";

// Icons as SVG components
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

interface DashboardStats {
  farmCount: number;
  plotCount: number;
  totalArea: string;
  activeCropCount: number;
  upcomingTaskCount: number;
}

export default function Home() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [currentTime, setCurrentTime] = useState("");
  const [stats, setStats] = useState<DashboardStats>({
    farmCount: 0,
    plotCount: 0,
    totalArea: "0",
    activeCropCount: 0,
    upcomingTaskCount: 0
  });

  useEffect(() => {
    // Check for saved farmer data
    const farmerData = localStorage.getItem("agriwise_farmer");
    if (farmerData) {
      setIsLoggedIn(true);
    }

    // Update time
    const updateTime = () => {
      const now = new Date();
      setCurrentTime(now.toLocaleTimeString("ar-DZ", { hour: "2-digit", minute: "2-digit" }));
    };
    updateTime();
    const interval = setInterval(updateTime, 60000);
    return () => clearInterval(interval);
  }, []);

  // Fetch real stats from database
  useEffect(() => {
    if (isLoggedIn) {
      fetch("/api/dashboard/stats")
        .then(res => res.json())
        .then(data => {
          if (data.success && data.stats) {
            setStats(data.stats);
          }
        })
        .catch(err => console.error("Failed to fetch stats:", err));
    }
  }, [isLoggedIn]);

  // Landing page for non-logged in users
  if (!isLoggedIn) {
    return (
      <main className="page" style={{ display: "flex", flexDirection: "column", justifyContent: "center", minHeight: "100vh", paddingBottom: "2rem" }}>
        {/* Hero Section */}
        <div className="slide-up" style={{ textAlign: "center", marginBottom: "3rem" }}>
          <div style={{ fontSize: "5rem", marginBottom: "1rem" }}>🌾</div>
          <h1 style={{ fontSize: "2.5rem", marginBottom: "0.5rem", background: "linear-gradient(135deg, #22c55e 0%, #16a34a 100%)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
            أجري وايز
          </h1>
          <p style={{ color: "var(--foreground-muted)", fontSize: "1.1rem", marginBottom: "0" }}>
            منصة ذكية للفلاحة الجزائرية
          </p>
          <p style={{ color: "var(--foreground-muted)", fontSize: "0.9rem", opacity: 0.7 }}>
            Algeria&apos;s Smart Agriculture Platform
          </p>
        </div>

        {/* Features */}
        <div className="fade-in" style={{ marginBottom: "2.5rem" }}>
          <div className="card" style={{ marginBottom: "1rem", display: "flex", alignItems: "center", gap: "1rem" }}>
            <div className="card-icon">📅</div>
            <div>
              <h3 style={{ margin: 0, fontSize: "1rem" }}>تقويم المحاصيل</h3>
              <p style={{ margin: 0, fontSize: "0.85rem" }}>تتبع مواعيد الزراعة والحصاد</p>
            </div>
          </div>

          <div className="card" style={{ marginBottom: "1rem", display: "flex", alignItems: "center", gap: "1rem" }}>
            <div className="card-icon">🌤️</div>
            <div>
              <h3 style={{ margin: 0, fontSize: "1rem" }}>تنبيهات الطقس</h3>
              <p style={{ margin: 0, fontSize: "0.85rem" }}>احمِ محاصيلك من التغيرات المناخية</p>
            </div>
          </div>

          <div className="card" style={{ marginBottom: "1rem", display: "flex", alignItems: "center", gap: "1rem" }}>
            <div className="card-icon">💡</div>
            <div>
              <h3 style={{ margin: 0, fontSize: "1rem" }}>نصائح زراعية</h3>
              <p style={{ margin: 0, fontSize: "0.85rem" }}>توصيات مخصصة لمحاصيلك</p>
            </div>
          </div>
        </div>

        {/* CTA Buttons */}
        <div className="fade-in" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          <Link href="/onboarding" className="btn btn-primary" style={{ textDecoration: "none" }}>
            ابدأ الآن - مجاني
          </Link>
          <button 
            className="btn btn-secondary"
            onClick={() => {
              // Demo mode - skip to dashboard
              localStorage.setItem("agriwise_farmer", JSON.stringify({
                phone: "0555000000",
                name: "فلاح تجريبي",
                wilaya: "17",
                wilayaName: "الجلفة"
              }));
              setIsLoggedIn(true);
            }}
          >
            تجربة النسخة التجريبية
          </button>
        </div>

        {/* Footer */}
        <div style={{ textAlign: "center", marginTop: "3rem", color: "var(--foreground-muted)", fontSize: "0.8rem" }}>
          <p>🇩🇿 صُنع في الجزائر</p>
        </div>
      </main>
    );
  }

  // Dashboard for logged in users
  return (
    <main className="page">
      {/* Header */}
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
        <div>
          <p style={{ margin: 0, color: "var(--foreground-muted)", fontSize: "0.9rem" }}>مرحباً 👋</p>
          <h1 style={{ fontSize: "1.5rem", margin: 0 }}>أهلاً بك في أجري وايز</h1>
        </div>
        <div style={{ textAlign: "left", direction: "ltr" }}>
          <p style={{ margin: 0, fontSize: "0.9rem", color: "var(--foreground-muted)" }}>{currentTime}</p>
        </div>
      </header>

      {/* Weather Card */}
      <div className="weather-card slide-up" style={{ marginBottom: "1.5rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <p style={{ margin: 0, opacity: 0.8, fontSize: "0.9rem" }}>الجلفة</p>
            <div className="weather-temp">18°</div>
            <p className="weather-condition" style={{ margin: 0 }}>صافٍ ومشمس</p>
          </div>
          <div style={{ fontSize: "4rem" }}>☀️</div>
        </div>
        <div style={{ marginTop: "1rem", display: "flex", gap: "1.5rem", fontSize: "0.85rem", opacity: 0.9 }}>
          <span>💧 رطوبة: 45%</span>
          <span>💨 رياح: 12 كم/س</span>
        </div>
      </div>

      {/* Stats */}
      <div className="stats-grid fade-in">
        <div className="stat-card">
          <div className="stat-value">{stats.farmCount}</div>
          <div className="stat-label">المزارع</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats.plotCount}</div>
          <div className="stat-label">القطع</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats.activeCropCount}</div>
          <div className="stat-label">المحاصيل النشطة</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats.upcomingTaskCount}</div>
          <div className="stat-label">المهام القادمة</div>
        </div>
      </div>

      {/* Alert */}
      <div className="alert alert-warning fade-in" style={{ marginBottom: "1.5rem" }}>
        <span style={{ fontSize: "1.5rem" }}>⚠️</span>
        <div>
          <strong>تنبيه طقس</strong>
          <p style={{ margin: 0, fontSize: "0.9rem" }}>توقع انخفاض درجات الحرارة الليلة. يُنصح بحماية الشتلات.</p>
        </div>
      </div>

      {/* Quick Actions */}
      <h2 style={{ fontSize: "1.1rem", marginBottom: "1rem" }}>إجراءات سريعة</h2>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.75rem", marginBottom: "1.5rem" }}>
        <Link href="/farm" className="card" style={{ textDecoration: "none", color: "inherit", padding: "1rem 0.5rem" }}>
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: "1.75rem", marginBottom: "0.25rem" }}>🚜</div>
            <p style={{ margin: 0, fontWeight: 600, fontSize: "0.85rem" }}>مزارعي</p>
          </div>
        </Link>
        <Link href="/calendar" className="card" style={{ textDecoration: "none", color: "inherit", padding: "1rem 0.5rem" }}>
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: "1.75rem", marginBottom: "0.25rem" }}>📅</div>
            <p style={{ margin: 0, fontWeight: 600, fontSize: "0.85rem" }}>التقويم</p>
          </div>
        </Link>
        <Link href="/weather" className="card" style={{ textDecoration: "none", color: "inherit", padding: "1rem 0.5rem" }}>
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: "1.75rem", marginBottom: "0.25rem" }}>🌦️</div>
            <p style={{ margin: 0, fontWeight: 600, fontSize: "0.85rem" }}>الطقس</p>
          </div>
        </Link>
        <Link href="/pests" className="card" style={{ textDecoration: "none", color: "inherit", padding: "1rem 0.5rem" }}>
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: "1.75rem", marginBottom: "0.25rem" }}>🐛</div>
            <p style={{ margin: 0, fontWeight: 600, fontSize: "0.85rem" }}>الآفات</p>
          </div>
        </Link>
        <Link href="/recommendations" className="card" style={{ textDecoration: "none", color: "inherit", padding: "1rem 0.5rem" }}>
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: "1.75rem", marginBottom: "0.25rem" }}>💡</div>
            <p style={{ margin: 0, fontWeight: 600, fontSize: "0.85rem" }}>نصائح</p>
          </div>
        </Link>
        <Link href="/advisor" className="card" style={{ textDecoration: "none", color: "inherit", padding: "1rem 0.5rem", background: "linear-gradient(135deg, rgba(59, 130, 246, 0.1), rgba(139, 92, 246, 0.2))" }}>
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: "1.75rem", marginBottom: "0.25rem" }}>🤖</div>
            <p style={{ margin: 0, fontWeight: 600, fontSize: "0.85rem" }}>المستشار</p>
          </div>
        </Link>
      </div>

      {/* Upcoming Tasks */}
      <h2 style={{ fontSize: "1.1rem", marginBottom: "1rem" }}>المهام القادمة</h2>
      <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
        <div className="card" style={{ padding: "1rem", display: "flex", alignItems: "center", gap: "1rem" }}>
          <div style={{ width: "48px", height: "48px", background: "rgba(34, 197, 94, 0.1)", borderRadius: "12px", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "1.5rem" }}>
            💧
          </div>
          <div style={{ flex: 1 }}>
            <h4 style={{ margin: 0, fontSize: "1rem" }}>سقي القمح</h4>
            <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--foreground-muted)" }}>قطعة الشمال - غداً</p>
          </div>
        </div>

        <div className="card" style={{ padding: "1rem", display: "flex", alignItems: "center", gap: "1rem" }}>
          <div style={{ width: "48px", height: "48px", background: "rgba(251, 191, 36, 0.1)", borderRadius: "12px", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "1.5rem" }}>
            🌱
          </div>
          <div style={{ flex: 1 }}>
            <h4 style={{ margin: 0, fontSize: "1rem" }}>تسميد البطاطا</h4>
            <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--foreground-muted)" }}>قطعة الجنوب - خلال 3 أيام</p>
          </div>
        </div>
      </div>

      {/* Bottom Navigation */}
      <nav className="nav-bottom">
        <Link href="/" className="nav-item active">
          <HomeIcon />
          <span>الرئيسية</span>
        </Link>
        <Link href="/farm" className="nav-item">
          <FarmIcon />
          <span>المزارع</span>
        </Link>
        <Link href="/calendar" className="nav-item">
          <CalendarIcon />
          <span>التقويم</span>
        </Link>
        <Link href="/weather" className="nav-item">
          <WeatherIcon />
          <span>الطقس</span>
        </Link>
        <Link href="/profile" className="nav-item">
          <UserIcon />
          <span>حسابي</span>
        </Link>
      </nav>
    </main>
  );
}

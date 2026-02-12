"use client";

import Link from "next/link";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";

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

interface FarmerData {
  phone: string;
  name: string;
  wilaya: string;
  wilayaName: string;
  commune?: string;
  farmName?: string;
  farmArea?: string;
}

export default function ProfilePage() {
  const router = useRouter();
  const [farmer, setFarmer] = useState<FarmerData | null>(null);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);

  useEffect(() => {
    const savedFarmer = localStorage.getItem("agriwise_farmer");
    if (savedFarmer) {
      setFarmer(JSON.parse(savedFarmer));
    } else {
      router.push("/onboarding");
    }
  }, [router]);

  const handleLogout = () => {
    localStorage.removeItem("agriwise_farmer");
    localStorage.removeItem("agriwise_farms");
    router.push("/");
    // Force page reload to reset state
    window.location.reload();
  };

  if (!farmer) {
    return (
      <main className="page" style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh" }}>
        <div className="spinner" />
      </main>
    );
  }

  return (
    <main className="page">
      {/* Header */}
      <header className="page-header">
        <h1 className="page-title">حسابي</h1>
        <p className="page-subtitle">إعدادات الحساب والملف الشخصي</p>
      </header>

      {/* Profile Card */}
      <div className="card slide-up" style={{ marginBottom: "1.5rem", textAlign: "center" }}>
        <div style={{ 
          width: "80px", 
          height: "80px", 
          borderRadius: "50%", 
          background: "linear-gradient(135deg, var(--color-primary-500), var(--color-primary-600))",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          margin: "0 auto 1rem",
          fontSize: "2.5rem"
        }}>
          👨‍🌾
        </div>
        <h2 style={{ margin: "0 0 0.25rem 0", fontSize: "1.25rem" }}>{farmer.name}</h2>
        <p style={{ margin: 0, color: "var(--foreground-muted)" }}>📍 {farmer.wilayaName}</p>
        {farmer.commune && (
          <p style={{ margin: "0.25rem 0 0 0", fontSize: "0.85rem", color: "var(--foreground-muted)" }}>{farmer.commune}</p>
        )}
      </div>

      {/* Info Cards */}
      <div className="fade-in" style={{ marginBottom: "1.5rem" }}>
        <h3 style={{ fontSize: "1rem", marginBottom: "1rem" }}>معلومات الحساب</h3>
        
        <div className="card" style={{ marginBottom: "0.75rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
            <div style={{ 
              width: "40px", 
              height: "40px", 
              borderRadius: "10px", 
              background: "rgba(34, 197, 94, 0.1)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "1.25rem"
            }}>
              📱
            </div>
            <div style={{ flex: 1 }}>
              <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--foreground-muted)" }}>رقم الهاتف</p>
              <p style={{ margin: 0, fontWeight: 600, direction: "ltr", textAlign: "right" }}>{farmer.phone}</p>
            </div>
          </div>
        </div>

        {farmer.farmName && (
          <div className="card" style={{ marginBottom: "0.75rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
              <div style={{ 
                width: "40px", 
                height: "40px", 
                borderRadius: "10px", 
                background: "rgba(34, 197, 94, 0.1)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "1.25rem"
              }}>
                🚜
              </div>
              <div style={{ flex: 1 }}>
                <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--foreground-muted)" }}>المزرعة الرئيسية</p>
                <p style={{ margin: 0, fontWeight: 600 }}>{farmer.farmName}</p>
              </div>
            </div>
          </div>
        )}

        {farmer.farmArea && (
          <div className="card">
            <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
              <div style={{ 
                width: "40px", 
                height: "40px", 
                borderRadius: "10px", 
                background: "rgba(34, 197, 94, 0.1)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "1.25rem"
              }}>
                📐
              </div>
              <div style={{ flex: 1 }}>
                <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--foreground-muted)" }}>المساحة الإجمالية</p>
                <p style={{ margin: 0, fontWeight: 600 }}>{farmer.farmArea} هكتار</p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Quick Links */}
      <div className="fade-in" style={{ marginBottom: "1.5rem" }}>
        <h3 style={{ fontSize: "1rem", marginBottom: "1rem" }}>روابط سريعة</h3>
        
        <Link href="/farm" className="card" style={{ display: "flex", alignItems: "center", gap: "1rem", marginBottom: "0.75rem", textDecoration: "none", color: "inherit" }}>
          <div style={{ fontSize: "1.5rem" }}>🚜</div>
          <div style={{ flex: 1 }}>
            <p style={{ margin: 0, fontWeight: 600 }}>إدارة المزارع</p>
            <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--foreground-muted)" }}>عرض وتعديل مزارعك</p>
          </div>
          <span style={{ color: "var(--foreground-muted)" }}>←</span>
        </Link>

        <Link href="/recommendations" className="card" style={{ display: "flex", alignItems: "center", gap: "1rem", marginBottom: "0.75rem", textDecoration: "none", color: "inherit" }}>
          <div style={{ fontSize: "1.5rem" }}>💡</div>
          <div style={{ flex: 1 }}>
            <p style={{ margin: 0, fontWeight: 600 }}>نصائح زراعية</p>
            <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--foreground-muted)" }}>توصيات لمحاصيلك</p>
          </div>
          <span style={{ color: "var(--foreground-muted)" }}>←</span>
        </Link>
      </div>

      {/* App Info */}
      <div className="fade-in" style={{ marginBottom: "1.5rem" }}>
        <div className="card" style={{ textAlign: "center", background: "var(--background-tertiary)" }}>
          <p style={{ margin: "0 0 0.5rem 0", fontSize: "1.5rem" }}>🌾</p>
          <p style={{ margin: "0 0 0.25rem 0", fontWeight: 600 }}>أجري وايز</p>
          <p style={{ margin: 0, fontSize: "0.8rem", color: "var(--foreground-muted)" }}>الإصدار 1.0.0</p>
          <p style={{ margin: "0.5rem 0 0 0", fontSize: "0.75rem", color: "var(--foreground-muted)" }}>🇩🇿 صُنع في الجزائر</p>
        </div>
      </div>

      {/* Logout Button */}
      <button 
        className="btn btn-secondary fade-in"
        style={{ width: "100%", marginBottom: "1rem" }}
        onClick={() => setShowLogoutConfirm(true)}
      >
        تسجيل الخروج
      </button>

      {/* Logout Confirmation Modal */}
      {showLogoutConfirm && (
        <div style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: "rgba(0, 0, 0, 0.5)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          zIndex: 1000,
          padding: "1rem"
        }}>
          <div className="card slide-up" style={{ maxWidth: "320px", width: "100%", textAlign: "center" }}>
            <div style={{ fontSize: "3rem", marginBottom: "1rem" }}>👋</div>
            <h3 style={{ margin: "0 0 0.5rem 0" }}>تسجيل الخروج</h3>
            <p style={{ margin: "0 0 1.5rem 0", color: "var(--foreground-muted)" }}>
              هل أنت متأكد من تسجيل الخروج من حسابك؟
            </p>
            <div style={{ display: "flex", gap: "0.75rem" }}>
              <button 
                className="btn btn-secondary"
                style={{ flex: 1 }}
                onClick={() => setShowLogoutConfirm(false)}
              >
                إلغاء
              </button>
              <button 
                className="btn btn-primary"
                style={{ flex: 1, background: "var(--color-error-500)" }}
                onClick={handleLogout}
              >
                خروج
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Bottom Navigation */}
      <nav className="nav-bottom">
        <Link href="/" className="nav-item">
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
        <Link href="/profile" className="nav-item active">
          <UserIcon />
          <span>حسابي</span>
        </Link>
      </nav>
    </main>
  );
}

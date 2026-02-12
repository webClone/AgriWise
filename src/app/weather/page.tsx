"use client";

import Link from "next/link";
import { useState, useEffect } from "react";

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

const RefreshIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" style={{ width: "20px", height: "20px" }}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
  </svg>
);

interface WeatherData {
  location: {
    latitude: number;
    longitude: number;
    wilaya: string;
  };
  current: {
    temperature: number;
    humidity: number;
    windSpeed: number;
    weatherCode: number;
    condition: string;
    conditionAr: string;
    icon: string;
  };
  daily: Array<{
    date: string;
    tempMax: number;
    tempMin: number;
    weatherCode: number;
    condition: string;
    conditionAr: string;
    icon: string;
    precipitationProbability: number;
    uvIndex: number;
  }>;
  alerts: Array<{
    type: string;
    severity: "info" | "warning" | "critical";
    message: string;
    messageAr: string;
    icon: string;
  }>;
}

const ARABIC_DAYS = ["الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت"];

export default function WeatherPage() {
  const [weather, setWeather] = useState<WeatherData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [wilayaCode, setWilayaCode] = useState("17"); // Default Djelfa
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchWeather = async (code: string) => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`/api/weather?wilaya=${code}`);
      const data = await response.json();
      
      if (data.success) {
        setWeather(data.data);
        setLastUpdated(new Date());
      } else {
        setError(data.error || "فشل الحصول على بيانات الطقس");
      }
    } catch (err) {
      console.error("Weather fetch error:", err);
      setError("تعذر الاتصال بخدمة الطقس");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Get user's wilaya from localStorage
    const farmerData = localStorage.getItem("agriwise_farmer");
    if (farmerData) {
      try {
        const farmer = JSON.parse(farmerData);
        if (farmer.wilaya) {
          setWilayaCode(farmer.wilaya);
        }
      } catch {}
    }
  }, []);

  useEffect(() => {
    fetchWeather(wilayaCode);
  }, [wilayaCode]);

  const formatDayName = (dateStr: string, index: number) => {
    if (index === 0) return "اليوم";
    if (index === 1) return "غداً";
    const date = new Date(dateStr);
    return ARABIC_DAYS[date.getDay()];
  };

  if (loading) {
    return (
      <main className="page" style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh" }}>
        <div className="spinner" />
      </main>
    );
  }

  if (error) {
    return (
      <main className="page">
        <header className="page-header">
          <h1 className="page-title">الطقس</h1>
        </header>
        <div className="alert alert-warning" style={{ marginBottom: "1rem" }}>
          <span style={{ fontSize: "1.5rem" }}>⚠️</span>
          <div>
            <strong>تعذر تحميل الطقس</strong>
            <p style={{ margin: 0, fontSize: "0.9rem" }}>{error}</p>
          </div>
        </div>
        <button className="btn btn-primary" onClick={() => fetchWeather(wilayaCode)}>
          <RefreshIcon /> إعادة المحاولة
        </button>
        
        {/* Bottom Navigation */}
        <nav className="nav-bottom">
          <Link href="/" className="nav-item"><HomeIcon /><span>الرئيسية</span></Link>
          <Link href="/farm" className="nav-item"><FarmIcon /><span>المزارع</span></Link>
          <Link href="/calendar" className="nav-item"><CalendarIcon /><span>التقويم</span></Link>
          <Link href="/weather" className="nav-item active"><WeatherIcon /><span>الطقس</span></Link>
          <Link href="/profile" className="nav-item"><UserIcon /><span>حسابي</span></Link>
        </nav>
      </main>
    );
  }

  if (!weather) return null;

  return (
    <main className="page">
      {/* Header */}
      <header className="page-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1 className="page-title">الطقس</h1>
          <p className="page-subtitle">📍 {weather.location.wilaya}</p>
        </div>
        <button 
          className="btn btn-icon btn-secondary" 
          onClick={() => fetchWeather(wilayaCode)}
          title="تحديث"
          style={{ marginTop: "0.5rem" }}
        >
          <RefreshIcon />
        </button>
      </header>

      {/* Last Updated */}
      {lastUpdated && (
        <p style={{ fontSize: "0.75rem", color: "var(--foreground-muted)", marginBottom: "1rem", textAlign: "center" }}>
          آخر تحديث: {lastUpdated.toLocaleTimeString("ar-DZ", { hour: "2-digit", minute: "2-digit" })}
        </p>
      )}

      {/* Current Weather */}
      <div className="weather-card slide-up" style={{ marginBottom: "1.5rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <div className="weather-temp">{weather.current.temperature}°</div>
            <p className="weather-condition" style={{ margin: 0 }}>{weather.current.conditionAr}</p>
          </div>
          <div style={{ fontSize: "5rem" }}>{weather.current.icon}</div>
        </div>
        <div style={{ 
          marginTop: "1.5rem", 
          display: "grid", 
          gridTemplateColumns: "repeat(3, 1fr)", 
          gap: "1rem",
          textAlign: "center"
        }}>
          <div>
            <div style={{ fontSize: "1.25rem" }}>💧</div>
            <div style={{ fontSize: "0.9rem", fontWeight: 600 }}>{weather.current.humidity}%</div>
            <div style={{ fontSize: "0.75rem", opacity: 0.8 }}>رطوبة</div>
          </div>
          <div>
            <div style={{ fontSize: "1.25rem" }}>💨</div>
            <div style={{ fontSize: "0.9rem", fontWeight: 600 }}>{weather.current.windSpeed} كم/س</div>
            <div style={{ fontSize: "0.75rem", opacity: 0.8 }}>رياح</div>
          </div>
          <div>
            <div style={{ fontSize: "1.25rem" }}>☀️</div>
            <div style={{ fontSize: "0.9rem", fontWeight: 600 }}>{weather.daily[0]?.uvIndex || 0}</div>
            <div style={{ fontSize: "0.75rem", opacity: 0.8 }}>الأشعة</div>
          </div>
        </div>
      </div>

      {/* Agricultural Alerts */}
      {weather.alerts.length > 0 && (
        <div className="fade-in" style={{ marginBottom: "1.5rem" }}>
          <h2 style={{ fontSize: "1.1rem", marginBottom: "1rem" }}>⚠️ تنبيهات زراعية</h2>
          {weather.alerts.map((alert, index) => (
            <div 
              key={index} 
              className={`alert ${alert.severity === "critical" ? "alert-warning" : alert.severity === "warning" ? "alert-warning" : "alert-success"}`}
              style={{ marginBottom: "0.5rem" }}
            >
              <span style={{ fontSize: "1.5rem" }}>{alert.icon}</span>
              <p style={{ margin: 0, fontSize: "0.9rem" }}>{alert.messageAr}</p>
            </div>
          ))}
        </div>
      )}

      {/* 7-Day Forecast */}
      <div className="fade-in">
        <h2 style={{ fontSize: "1.1rem", marginBottom: "1rem" }}>توقعات 7 أيام</h2>
        <div className="card" style={{ padding: 0 }}>
          {weather.daily.map((day, index) => (
            <div 
              key={index}
              style={{ 
                display: "flex", 
                alignItems: "center", 
                padding: "1rem",
                borderBottom: index < weather.daily.length - 1 ? "1px solid var(--background-tertiary)" : "none"
              }}
            >
              <div style={{ flex: 1, fontWeight: index === 0 ? 600 : 400 }}>
                {formatDayName(day.date, index)}
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginLeft: "1rem", marginRight: "1rem" }}>
                <span style={{ fontSize: "1.5rem" }}>{day.icon}</span>
                {day.precipitationProbability > 30 && (
                  <span style={{ fontSize: "0.75rem", color: "var(--color-water-500)" }}>
                    {day.precipitationProbability}%
                  </span>
                )}
              </div>
              <div style={{ display: "flex", gap: "0.75rem", direction: "ltr", minWidth: "70px", justifyContent: "flex-end" }}>
                <span style={{ fontWeight: 600 }}>{day.tempMax}°</span>
                <span style={{ color: "var(--foreground-muted)" }}>{day.tempMin}°</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Agricultural Tips */}
      <div className="fade-in" style={{ marginTop: "1.5rem" }}>
        <h2 style={{ fontSize: "1.1rem", marginBottom: "1rem" }}>💡 نصائح بناءً على الطقس</h2>
        <div className="card">
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {weather.current.temperature < 10 && (
              <li style={{ padding: "0.75rem 0", borderBottom: "1px solid var(--background-tertiary)", display: "flex", gap: "0.75rem" }}>
                <span>❄️</span>
                <span>درجة الحرارة منخفضة - احمِ الشتلات الحساسة</span>
              </li>
            )}
            {weather.current.temperature >= 35 && (
              <li style={{ padding: "0.75rem 0", borderBottom: "1px solid var(--background-tertiary)", display: "flex", gap: "0.75rem" }}>
                <span>🥵</span>
                <span>درجة الحرارة مرتفعة - زد الري واختر الأوقات المناسبة</span>
              </li>
            )}
            {weather.current.humidity < 40 && (
              <li style={{ padding: "0.75rem 0", borderBottom: "1px solid var(--background-tertiary)", display: "flex", gap: "0.75rem" }}>
                <span>💧</span>
                <span>الرطوبة منخفضة - راقب احتياجات الري</span>
              </li>
            )}
            {weather.current.windSpeed >= 30 && (
              <li style={{ padding: "0.75rem 0", borderBottom: "1px solid var(--background-tertiary)", display: "flex", gap: "0.75rem" }}>
                <span>💨</span>
                <span>رياح قوية - أجّل عمليات الرش</span>
              </li>
            )}
            {weather.daily.some(d => d.precipitationProbability > 50) && (
              <li style={{ padding: "0.75rem 0", display: "flex", gap: "0.75rem" }}>
                <span>🌧️</span>
                <span>أمطار متوقعة - يمكن تأجيل الري</span>
              </li>
            )}
            {weather.current.temperature >= 15 && weather.current.temperature <= 30 && weather.current.humidity >= 40 && (
              <li style={{ padding: "0.75rem 0", display: "flex", gap: "0.75rem" }}>
                <span>🌡️</span>
                <span>ظروف مثالية للنمو - استمر بالرعاية المعتادة</span>
              </li>
            )}
          </ul>
        </div>
      </div>

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
        <Link href="/weather" className="nav-item active">
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

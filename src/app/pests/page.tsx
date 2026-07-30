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

interface PestReport {
  id: string;
  type: string;
  name: string | null;
  nameAr: string | null;
  severity: string;
  description: string | null;
  wilayaCode: string;
  cropAffected: string | null;
  status: string;
  createdAt: string;
  reporter: { name: string; wilaya: string };
}

const commonPests = [
  { code: "locust", nameAr: "الجراد", icon: "🦗" },
  { code: "aphid", nameAr: "المن", icon: "🐛" },
  { code: "whitefly", nameAr: "الذبابة البيضاء", icon: "🪰" },
  { code: "mite", nameAr: "العنكبوت الأحمر", icon: "🕷️" },
  { code: "snail", nameAr: "الحلزون", icon: "🐌" },
  { code: "worm", nameAr: "الديدان", icon: "🪱" },
];

const commonDiseases = [
  { code: "rust", nameAr: "الصدأ", icon: "🟤" },
  { code: "mildew", nameAr: "البياض الدقيقي", icon: "⬜" },
  { code: "blight", nameAr: "اللفحة", icon: "🟫" },
  { code: "wilt", nameAr: "الذبول", icon: "🥀" },
  { code: "rot", nameAr: "العفن", icon: "🟢" },
  { code: "virus", nameAr: "فيروس", icon: "🦠" },
];

export default function PestsPage() {
  const [activeTab, setActiveTab] = useState<"alerts" | "report">("alerts");
  const [reports, setReports] = useState<PestReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [showReportForm, setShowReportForm] = useState(false);
  const [reportType, setReportType] = useState<"pest" | "disease">("pest");
  const [selectedPest, setSelectedPest] = useState<string>("");
  const [severity, setSeverity] = useState<string>("WARNING");
  const [description, setDescription] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    fetchReports();
  }, []);

  const fetchReports = async () => {
    try {
      // Get user's wilaya
      const farmerData = localStorage.getItem("agriwise_farmer");
      let wilayaCode = "17"; // Default
      if (farmerData) {
        const farmer = JSON.parse(farmerData);
        wilayaCode = farmer.wilaya || "17";
      }

      const response = await fetch(`/api/pests?wilaya=${wilayaCode}&limit=20`);
      const data = await response.json();
      
      if (data.success) {
        setReports(data.data.reports || []);
      }
    } catch (error) {
      console.error("Failed to fetch pest reports:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitReport = async () => {
    if (!selectedPest || !severity) {
      setMessage({ type: "error", text: "يرجى اختيار نوع الآفة والخطورة" });
      return;
    }

    setSubmitting(true);
    setMessage(null);

    try {
      // Get user's location and info
      const farmerData = localStorage.getItem("agriwise_farmer");
      if (!farmerData) {
        setMessage({ type: "error", text: "يرجى تسجيل الدخول أولاً" });
        return;
      }
      const farmer = JSON.parse(farmerData);

      // Get current location
      let latitude = 34.67;
      let longitude = 3.25;
      
      if (navigator.geolocation) {
        try {
          const position = await new Promise<GeolocationPosition>((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 5000 });
          });
          latitude = position.coords.latitude;
          longitude = position.coords.longitude;
        } catch {
          console.log("Using default location");
        }
      }

      const items = reportType === "pest" ? commonPests : commonDiseases;
      const selected = items.find(p => p.code === selectedPest);

      const response = await fetch("/api/pests", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          reporterId: farmer.id || "demo-user",
          type: reportType,
          name: selectedPest,
          nameAr: selected?.nameAr,
          latitude,
          longitude,
          wilayaCode: farmer.wilaya || "17",
          severity,
          description,
        }),
      });

      const data = await response.json();

      if (data.success) {
        setMessage({ type: "success", text: "تم إرسال البلاغ بنجاح! شكراً لمساهمتك." });
        setShowReportForm(false);
        setSelectedPest("");
        setDescription("");
        fetchReports();
      } else {
        setMessage({ type: "error", text: data.error || "فشل إرسال البلاغ" });
      }
    } catch (error) {
      console.error("Submit error:", error);
      setMessage({ type: "error", text: "حدث خطأ. حاول مرة أخرى." });
    } finally {
      setSubmitting(false);
    }
  };

  const getSeverityStyle = (severity: string) => {
    switch (severity) {
      case "CRITICAL":
        return { bg: "rgba(239, 68, 68, 0.1)", color: "var(--color-error-500)", label: "خطير" };
      case "WARNING":
        return { bg: "rgba(251, 191, 36, 0.1)", color: "var(--color-warning-500)", label: "متوسط" };
      default:
        return { bg: "rgba(34, 197, 94, 0.1)", color: "var(--color-primary-500)", label: "منخفض" };
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case "VERIFIED": return "مؤكد";
      case "INVESTIGATING": return "قيد التحقيق";
      case "RESOLVED": return "تم الحل";
      case "FALSE_ALARM": return "إنذار كاذب";
      default: return "جديد";
    }
  };

  return (
    <main className="page">
      {/* Header */}
      <header className="page-header">
        <h1 className="page-title">الآفات والأمراض</h1>
        <p className="page-subtitle">شبكة الإنذار المبكر</p>
      </header>

      {/* Message */}
      {message && (
        <div className={`alert ${message.type === "success" ? "alert-success" : "alert-warning"} fade-in`} style={{ marginBottom: "1rem" }}>
          <span style={{ fontSize: "1.5rem" }}>{message.type === "success" ? "✅" : "⚠️"}</span>
          <p style={{ margin: 0 }}>{message.text}</p>
        </div>
      )}

      {/* Tabs */}
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1.5rem" }}>
        <button
          className={`btn ${activeTab === "alerts" ? "btn-primary" : "btn-secondary"}`}
          onClick={() => setActiveTab("alerts")}
          style={{ flex: 1 }}
        >
          🔔 التنبيهات
        </button>
        <button
          className={`btn ${activeTab === "report" ? "btn-primary" : "btn-secondary"}`}
          onClick={() => setActiveTab("report")}
          style={{ flex: 1 }}
        >
          📝 إبلاغ
        </button>
      </div>

      {/* Alerts Tab */}
      {activeTab === "alerts" && (
        <div className="fade-in">
          {loading ? (
            <div style={{ textAlign: "center", padding: "2rem" }}>
              <div className="spinner" />
            </div>
          ) : reports.length === 0 ? (
            <div className="empty-state">
              <div className="emoji">🛡️</div>
              <div className="title">لا توجد تنبيهات حالياً</div>
              <div className="subtitle">منطقتك خالية من التقارير الحديثة</div>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              {reports.map((report) => {
                const sevStyle = getSeverityStyle(report.severity);
                return (
                  <div key={report.id} className="card" style={{ padding: "1rem" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "0.5rem" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                        <span style={{ fontSize: "1.5rem" }}>
                          {report.type === "pest" ? "🐛" : "🦠"}
                        </span>
                        <div>
                          <h4 style={{ margin: 0, fontSize: "1rem" }}>
                            {report.nameAr || report.name || "غير معروف"}
                          </h4>
                          <p style={{ margin: 0, fontSize: "0.8rem", color: "var(--foreground-muted)" }}>
                            {report.cropAffected || "محاصيل متعددة"}
                          </p>
                        </div>
                      </div>
                      <span style={{ 
                        padding: "0.2rem 0.5rem", 
                        borderRadius: "var(--radius-full)",
                        fontSize: "0.75rem",
                        fontWeight: 600,
                        background: sevStyle.bg,
                        color: sevStyle.color
                      }}>
                        {sevStyle.label}
                      </span>
                    </div>
                    {report.description && (
                      <p style={{ margin: "0.5rem 0", fontSize: "0.9rem", color: "var(--foreground-muted)" }}>
                        {report.description}
                      </p>
                    )}
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", color: "var(--foreground-muted)" }}>
                      <span>📍 {report.reporter?.wilaya || "غير معروف"}</span>
                      <span>{getStatusLabel(report.status)}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Report Tab */}
      {activeTab === "report" && (
        <div className="fade-in">
          {!showReportForm ? (
            <>
              <div className="alert alert-success" style={{ marginBottom: "1.5rem" }}>
                <span style={{ fontSize: "1.5rem" }}>🤝</span>
                <div>
                  <strong>ساهم في حماية المحاصيل</strong>
                  <p style={{ margin: 0, fontSize: "0.9rem" }}>
                    بلاغك يساعد المزارعين في منطقتك على اتخاذ الإجراءات الوقائية
                  </p>
                </div>
              </div>
              <button 
                className="btn btn-primary" 
                style={{ width: "100%", marginBottom: "1.5rem" }}
                onClick={() => setShowReportForm(true)}
              >
                ➕ إبلاغ عن آفة أو مرض
              </button>
            </>
          ) : (
            <div className="card slide-up">
              <h3 style={{ margin: "0 0 1rem 0" }}>إبلاغ جديد</h3>
              
              {/* Type Selection */}
              <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
                <button
                  className={`btn ${reportType === "pest" ? "btn-primary" : "btn-secondary"}`}
                  onClick={() => { setReportType("pest"); setSelectedPest(""); }}
                  style={{ flex: 1 }}
                >
                  🐛 آفة
                </button>
                <button
                  className={`btn ${reportType === "disease" ? "btn-primary" : "btn-secondary"}`}
                  onClick={() => { setReportType("disease"); setSelectedPest(""); }}
                  style={{ flex: 1 }}
                >
                  🦠 مرض
                </button>
              </div>

              {/* Pest/Disease Selection */}
              <div className="input-group">
                <label className="input-label">
                  {reportType === "pest" ? "نوع الآفة" : "نوع المرض"}
                </label>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.5rem" }}>
                  {(reportType === "pest" ? commonPests : commonDiseases).map((item) => (
                    <button
                      key={item.code}
                      className={`btn ${selectedPest === item.code ? "btn-primary" : "btn-secondary"}`}
                      onClick={() => setSelectedPest(item.code)}
                      style={{ padding: "0.75rem 0.5rem", fontSize: "0.85rem" }}
                    >
                      <span style={{ display: "block", fontSize: "1.25rem", marginBottom: "0.25rem" }}>{item.icon}</span>
                      {item.nameAr}
                    </button>
                  ))}
                </div>
              </div>

              {/* Severity */}
              <div className="input-group">
                <label className="input-label">درجة الخطورة</label>
                <div style={{ display: "flex", gap: "0.5rem" }}>
                  {[
                    { value: "INFO", label: "منخفض", color: "var(--color-primary-500)" },
                    { value: "WARNING", label: "متوسط", color: "var(--color-warning-500)" },
                    { value: "CRITICAL", label: "خطير", color: "var(--color-error-500)" },
                  ].map((sev) => (
                    <button
                      key={sev.value}
                      className="btn btn-secondary"
                      onClick={() => setSeverity(sev.value)}
                      style={{ 
                        flex: 1, 
                        borderColor: severity === sev.value ? sev.color : "transparent",
                        borderWidth: "2px",
                        color: severity === sev.value ? sev.color : undefined,
                      }}
                    >
                      {sev.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Description */}
              <div className="input-group">
                <label className="input-label">وصف إضافي (اختياري)</label>
                <textarea
                  className="input"
                  rows={3}
                  placeholder="صف ما تراه..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  style={{ resize: "vertical" }}
                />
              </div>

              {/* Actions */}
              <div style={{ display: "flex", gap: "0.5rem", marginTop: "1rem" }}>
                <button 
                  className="btn btn-secondary" 
                  onClick={() => setShowReportForm(false)}
                  style={{ flex: 1 }}
                >
                  إلغاء
                </button>
                <button 
                  className="btn btn-primary" 
                  onClick={handleSubmitReport}
                  disabled={submitting || !selectedPest}
                  style={{ flex: 2 }}
                >
                  {submitting ? <div className="spinner" style={{ width: "20px", height: "20px" }} /> : "إرسال البلاغ"}
                </button>
              </div>
            </div>
          )}

          {/* Recent Reports */}
          {!showReportForm && reports.length > 0 && (
            <div style={{ marginTop: "1.5rem" }}>
              <h3 style={{ fontSize: "1rem", marginBottom: "1rem" }}>📋 آخر البلاغات</h3>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                {reports.slice(0, 5).map((report) => (
                  <div key={report.id} className="card" style={{ padding: "0.75rem", display: "flex", alignItems: "center", gap: "0.75rem" }}>
                    <span style={{ fontSize: "1.25rem" }}>{report.type === "pest" ? "🐛" : "🦠"}</span>
                    <div style={{ flex: 1 }}>
                      <p style={{ margin: 0, fontSize: "0.9rem" }}>{report.nameAr || report.name}</p>
                    </div>
                    <span style={{ fontSize: "0.75rem", color: "var(--foreground-muted)" }}>
                      {new Date(report.createdAt).toLocaleDateString("ar-DZ")}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Bottom Navigation */}
      <nav className="nav-bottom">
        <Link href="/" className="nav-item"><HomeIcon /><span>الرئيسية</span></Link>
        <Link href="/farm" className="nav-item"><FarmIcon /><span>المزارع</span></Link>
        <Link href="/calendar" className="nav-item"><CalendarIcon /><span>التقويم</span></Link>
        <Link href="/weather" className="nav-item"><WeatherIcon /><span>الطقس</span></Link>
        <Link href="/profile" className="nav-item"><UserIcon /><span>حسابي</span></Link>
      </nav>
    </main>
  );
}

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import wilayas from "@/data/algeria/wilayas.json";

interface Wilaya {
  code: string;
  nameAr: string;
  nameFr: string;
  nameEn: string;
}

export default function NewFarmPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    name: "",
    wilaya: "",
    commune: "",
    totalArea: "",
    waterSource: "",
    irrigationType: "",
    soilType: "",
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      const res = await fetch("/api/farms", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...formData,
          totalArea: parseFloat(formData.totalArea),
        }),
      });

      if (res.ok) {
        router.push("/farm");
        router.refresh();
      } else {
        alert("Error creating farm");
      }
    } catch (error) {
      console.error(error);
      alert("Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  return (
    <div className="page" style={{ background: "var(--background)", minHeight: "100vh", paddingBottom: "100px" }}>
      <div style={{ maxWidth: "500px", margin: "0 auto", padding: "1rem" }}>
        {/* Header */}
        <div className="card" style={{ marginBottom: "1rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <h1 className="page-title">إضافة مزرعة جديدة</h1>
              <p className="page-subtitle">أدخل بيانات مزرعتك</p>
            </div>
            <Link href="/farm" className="btn btn-secondary" style={{ padding: "0.5rem" }}>
              ✕
            </Link>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit}>
          {/* Basic Info Section */}
          <div className="card" style={{ marginBottom: "1rem" }}>
            <h3 style={{ color: "var(--color-primary-500)", marginBottom: "1rem", fontSize: "0.875rem", fontWeight: "bold" }}>
              🚜 معلومات أساسية
            </h3>
            
            <div className="input-group">
              <label className="input-label">اسم المزرعة *</label>
              <input
                type="text"
                name="name"
                required
                className="input"
                placeholder="مثال: مزرعة البركة"
                value={formData.name}
                onChange={handleChange}
              />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
              <div className="input-group">
                <label className="input-label">المساحة (هكتار) *</label>
                <input
                  type="number"
                  name="totalArea"
                  required
                  step="0.1"
                  className="input"
                  placeholder="0.0"
                  value={formData.totalArea}
                  onChange={handleChange}
                />
              </div>
              <div className="input-group">
                <label className="input-label">البلدية</label>
                <input
                  type="text"
                  name="commune"
                  className="input"
                  placeholder="اسم البلدية"
                  value={formData.commune}
                  onChange={handleChange}
                />
              </div>
            </div>

            <div className="input-group">
              <label className="input-label">الولاية *</label>
              <select
                name="wilaya"
                required
                className="input select"
                value={formData.wilaya}
                onChange={handleChange}
              >
                <option value="">اختر الولاية</option>
                {wilayas.wilayas.map((w: Wilaya) => (
                  <option key={w.code} value={w.nameAr}>{w.code} - {w.nameAr}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Soil & Water Section */}
          <div className="card" style={{ marginBottom: "1rem" }}>
            <h3 style={{ color: "var(--color-water-500)", marginBottom: "1rem", fontSize: "0.875rem", fontWeight: "bold" }}>
              💧 خصائص التربة والري
            </h3>
            
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.75rem" }}>
              <div className="input-group">
                <label className="input-label">نوع التربة</label>
                <select
                  name="soilType"
                  className="input select"
                  value={formData.soilType}
                  onChange={handleChange}
                >
                  <option value="">غير محدد</option>
                  <option value="CLAY">طينية</option>
                  <option value="SANDY">رملية</option>
                  <option value="LOAM">طميية</option>
                  <option value="SILT">غرينية</option>
                </select>
              </div>

              <div className="input-group">
                <label className="input-label">مصدر المياه</label>
                <select
                  name="waterSource"
                  className="input select"
                  value={formData.waterSource}
                  onChange={handleChange}
                >
                  <option value="">غير محدد</option>
                  <option value="WELL">بئر</option>
                  <option value="DAM">سد</option>
                  <option value="RIVER">نهر</option>
                  <option value="RAINFED">مطري</option>
                </select>
              </div>

              <div className="input-group">
                <label className="input-label">نظام الري</label>
                <select
                  name="irrigationType"
                  className="input select"
                  value={formData.irrigationType}
                  onChange={handleChange}
                >
                  <option value="">غير محدد</option>
                  <option value="DRIP">تقطير</option>
                  <option value="SPRINKLER">رش</option>
                  <option value="FLOOD">غمر</option>
                </select>
              </div>
            </div>
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={loading}
            className="btn btn-primary"
            style={{ width: "100%" }}
          >
            {loading ? "جاري الحفظ..." : "💾 حفظ المزرعة"}
          </button>
        </form>
      </div>

      {/* Bottom Navigation */}
      <nav className="nav-bottom">
        <Link href="/" className="nav-item">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" style={{ width: "24px", height: "24px" }}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12l8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75M8.25 21h8.25" />
          </svg>
          <span>الرئيسية</span>
        </Link>
        <Link href="/farm" className="nav-item active">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" style={{ width: "24px", height: "24px" }}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v2.25m6.364.386l-1.591 1.591M21 12h-2.25m-.386 6.364l-1.591-1.591M12 18.75V21m-4.773-4.227l-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z" />
          </svg>
          <span>المزارع</span>
        </Link>
        <Link href="/calendar" className="nav-item">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" style={{ width: "24px", height: "24px" }}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
          </svg>
          <span>التقويم</span>
        </Link>
        <Link href="/weather" className="nav-item">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" style={{ width: "24px", height: "24px" }}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15a4.5 4.5 0 004.5 4.5H18a3.75 3.75 0 001.332-7.257 3 3 0 00-3.758-3.848 5.25 5.25 0 00-10.233 2.33A4.502 4.502 0 002.25 15z" />
          </svg>
          <span>الطقس</span>
        </Link>
        <Link href="/profile" className="nav-item">
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" style={{ width: "24px", height: "24px" }}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
          </svg>
          <span>حسابي</span>
        </Link>
      </nav>
    </div>
  );
}

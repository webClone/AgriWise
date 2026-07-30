"use client";

import Link from "next/link";
import { useState } from "react";
import cropsData from "@/data/algeria/crops.json";

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

interface CropRecommendation {
  code: string;
  nameAr: string;
  icon: string;
  category: string;
  waterNeeds: string;
  plantingSeason: string;
  harvestSeason: string;
  tips: string[];
}

const cropRecommendations: CropRecommendation[] = [
  {
    code: "wheat",
    nameAr: "القمح",
    icon: "🌾",
    category: "حبوب",
    waterNeeds: "متوسط",
    plantingSeason: "أكتوبر - ديسمبر",
    harvestSeason: "مايو - يونيو",
    tips: [
      "اختر أصناف مقاومة للجفاف",
      "الري بالتقطير يوفر 40% من الماء",
      "التسميد النيتروجيني في مرحلة الإشطاء",
      "مراقبة الأمراض الفطرية في الربيع"
    ]
  },
  {
    code: "barley",
    nameAr: "الشعير",
    icon: "🌿",
    category: "حبوب",
    waterNeeds: "منخفض",
    plantingSeason: "أكتوبر - نوفمبر",
    harvestSeason: "أبريل - مايو",
    tips: [
      "يتحمل الملوحة أكثر من القمح",
      "مناسب للأراضي الهامشية",
      "حصاد مبكر قبل تساقط السنابل",
      "تخزين في مكان جاف وبارد"
    ]
  },
  {
    code: "potato",
    nameAr: "البطاطا",
    icon: "🥔",
    category: "خضروات",
    waterNeeds: "عالي",
    plantingSeason: "فبراير - مارس / سبتمبر",
    harvestSeason: "يونيو / ديسمبر",
    tips: [
      "زراعة درنات معتمدة وخالية من الأمراض",
      "تغطية الدرنات بالتراب لمنع الاخضرار",
      "الري المنتظم خاصة في مرحلة التدرن",
      "التبكير في الحصاد للأسعار الأفضل"
    ]
  },
  {
    code: "olive",
    nameAr: "الزيتون",
    icon: "🫒",
    category: "أشجار مثمرة",
    waterNeeds: "منخفض",
    plantingSeason: "نوفمبر - فبراير",
    harvestSeason: "أكتوبر - ديسمبر",
    tips: [
      "التقليم السنوي لتجديد الأغصان",
      "مكافحة ذبابة الزيتون في الصيف",
      "الحصاد عند تغير اللون",
      "العصر المبكر للجودة العالية"
    ]
  },
  {
    code: "date",
    nameAr: "التمر",
    icon: "🌴",
    category: "أشجار مثمرة",
    waterNeeds: "متوسط",
    plantingSeason: "مارس - أبريل",
    harvestSeason: "سبتمبر - نوفمبر",
    tips: [
      "التلقيح اليدوي يزيد الإنتاج",
      "تخفيف العراجين للحجم الأفضل",
      "حماية الثمار من الطيور والحشرات",
      "التجفيف الصحيح للتخزين الطويل"
    ]
  },
  {
    code: "tomato",
    nameAr: "الطماطم",
    icon: "🍅",
    category: "خضروات",
    waterNeeds: "عالي",
    plantingSeason: "فبراير - أبريل / أغسطس",
    harvestSeason: "مايو - يوليو / نوفمبر",
    tips: [
      "التربية على الأعمدة تحسن التهوية",
      "إزالة الفروع الجانبية للإنتاج المبكر",
      "الري بالتقطير في الصباح الباكر",
      "مراقبة الذبول الفيوزاري والنيماتودا"
    ]
  }
];

export default function RecommendationsPage() {
  const [selectedCrop, setSelectedCrop] = useState<string | null>(null);
  const [activeCategory, setActiveCategory] = useState<string>("الكل");

  const categories = ["الكل", "حبوب", "خضروات", "أشجار مثمرة"];

  const filteredCrops = activeCategory === "الكل" 
    ? cropRecommendations 
    : cropRecommendations.filter(crop => crop.category === activeCategory);

  const selectedCropData = cropRecommendations.find(c => c.code === selectedCrop);

  return (
    <main className="page">
      {/* Header */}
      <header className="page-header">
        <h1 className="page-title">نصائح زراعية</h1>
        <p className="page-subtitle">دليل شامل لمحاصيلك</p>
      </header>

      {/* Season Alert */}
      <div className="alert alert-success slide-up" style={{ marginBottom: "1.5rem" }}>
        <span style={{ fontSize: "1.5rem" }}>📅</span>
        <div>
          <strong>موسم الزراعة الشتوية</strong>
          <p style={{ margin: 0, fontSize: "0.9rem" }}>
            يناير مناسب لتحضير الأرض وزراعة الخضروات الشتوية
          </p>
        </div>
      </div>

      {/* Category Filter */}
      <div className="fade-in" style={{ 
        display: "flex", 
        gap: "0.5rem", 
        overflowX: "auto", 
        marginBottom: "1.5rem",
        paddingBottom: "0.5rem"
      }}>
        {categories.map((cat) => (
          <button
            key={cat}
            className={`btn ${activeCategory === cat ? "btn-primary" : "btn-secondary"}`}
            style={{ 
              whiteSpace: "nowrap", 
              padding: "0.5rem 1rem",
              fontSize: "0.9rem"
            }}
            onClick={() => setActiveCategory(cat)}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Crop Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "0.75rem", marginBottom: "1.5rem" }}>
        {filteredCrops.map((crop) => (
          <div
            key={crop.code}
            className="card fade-in"
            style={{ 
              cursor: "pointer",
              borderColor: selectedCrop === crop.code ? "var(--color-primary-500)" : "transparent",
              borderWidth: "2px",
              borderStyle: "solid"
            }}
            onClick={() => setSelectedCrop(selectedCrop === crop.code ? null : crop.code)}
          >
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: "2.5rem", marginBottom: "0.5rem" }}>{crop.icon}</div>
              <h3 style={{ margin: "0 0 0.25rem 0", fontSize: "1rem" }}>{crop.nameAr}</h3>
              <span style={{ 
                fontSize: "0.75rem", 
                padding: "0.2rem 0.5rem", 
                background: "var(--background-tertiary)", 
                borderRadius: "var(--radius-full)"
              }}>
                {crop.category}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Selected Crop Details */}
      {selectedCropData && (
        <div className="card slide-up" style={{ marginBottom: "1.5rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "1rem", marginBottom: "1rem" }}>
            <div style={{ fontSize: "3rem" }}>{selectedCropData.icon}</div>
            <div>
              <h2 style={{ margin: 0, fontSize: "1.25rem" }}>{selectedCropData.nameAr}</h2>
              <p style={{ margin: 0, color: "var(--foreground-muted)", fontSize: "0.9rem" }}>{selectedCropData.category}</p>
            </div>
          </div>

          {/* Info Grid */}
          <div style={{ 
            display: "grid", 
            gridTemplateColumns: "repeat(3, 1fr)", 
            gap: "0.75rem",
            marginBottom: "1rem"
          }}>
            <div style={{ textAlign: "center", padding: "0.75rem", background: "var(--background-tertiary)", borderRadius: "var(--radius-md)" }}>
              <div style={{ fontSize: "1.25rem", marginBottom: "0.25rem" }}>💧</div>
              <div style={{ fontSize: "0.75rem", color: "var(--foreground-muted)" }}>احتياج الماء</div>
              <div style={{ fontSize: "0.85rem", fontWeight: 600 }}>{selectedCropData.waterNeeds}</div>
            </div>
            <div style={{ textAlign: "center", padding: "0.75rem", background: "var(--background-tertiary)", borderRadius: "var(--radius-md)" }}>
              <div style={{ fontSize: "1.25rem", marginBottom: "0.25rem" }}>🌱</div>
              <div style={{ fontSize: "0.75rem", color: "var(--foreground-muted)" }}>الزراعة</div>
              <div style={{ fontSize: "0.85rem", fontWeight: 600 }}>{selectedCropData.plantingSeason.split(" ")[0]}</div>
            </div>
            <div style={{ textAlign: "center", padding: "0.75rem", background: "var(--background-tertiary)", borderRadius: "var(--radius-md)" }}>
              <div style={{ fontSize: "1.25rem", marginBottom: "0.25rem" }}>🌾</div>
              <div style={{ fontSize: "0.75rem", color: "var(--foreground-muted)" }}>الحصاد</div>
              <div style={{ fontSize: "0.85rem", fontWeight: 600 }}>{selectedCropData.harvestSeason.split(" ")[0]}</div>
            </div>
          </div>

          {/* Tips */}
          <h3 style={{ margin: "0 0 0.75rem 0", fontSize: "1rem" }}>💡 نصائح مهمة</h3>
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {selectedCropData.tips.map((tip, index) => (
              <li 
                key={index}
                style={{ 
                  padding: "0.75rem",
                  borderBottom: index < selectedCropData.tips.length - 1 ? "1px solid var(--background-tertiary)" : "none",
                  display: "flex",
                  gap: "0.75rem",
                  alignItems: "flex-start"
                }}
              >
                <span style={{ color: "var(--color-primary-500)" }}>✓</span>
                <span style={{ fontSize: "0.9rem" }}>{tip}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* General Tips */}
      <div className="fade-in" style={{ marginBottom: "1.5rem" }}>
        <h2 style={{ fontSize: "1.1rem", marginBottom: "1rem" }}>📚 نصائح عامة</h2>
        
        <div className="card" style={{ marginBottom: "0.75rem" }}>
          <div style={{ display: "flex", gap: "1rem", alignItems: "flex-start" }}>
            <div style={{ fontSize: "1.5rem" }}>🌡️</div>
            <div>
              <h4 style={{ margin: "0 0 0.25rem 0", fontSize: "0.95rem" }}>متابعة الطقس</h4>
              <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--foreground-muted)" }}>
                راقب توقعات الطقس يومياً لتخطيط عمليات الري والرش
              </p>
            </div>
          </div>
        </div>

        <div className="card" style={{ marginBottom: "0.75rem" }}>
          <div style={{ display: "flex", gap: "1rem", alignItems: "flex-start" }}>
            <div style={{ fontSize: "1.5rem" }}>💧</div>
            <div>
              <h4 style={{ margin: "0 0 0.25rem 0", fontSize: "0.95rem" }}>الري الذكي</h4>
              <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--foreground-muted)" }}>
                الري في الصباح الباكر أو المساء يقلل التبخر
              </p>
            </div>
          </div>
        </div>

        <div className="card">
          <div style={{ display: "flex", gap: "1rem", alignItems: "flex-start" }}>
            <div style={{ fontSize: "1.5rem" }}>🔄</div>
            <div>
              <h4 style={{ margin: "0 0 0.25rem 0", fontSize: "0.95rem" }}>الدورة الزراعية</h4>
              <p style={{ margin: 0, fontSize: "0.85rem", color: "var(--foreground-muted)" }}>
                تناوب المحاصيل يحسن خصوبة التربة ويقلل الآفات
              </p>
            </div>
          </div>
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

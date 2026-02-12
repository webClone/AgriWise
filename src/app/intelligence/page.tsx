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

const crops = [
  { code: "wheat", nameAr: "قمح", icon: "🌾" },
  { code: "barley", nameAr: "شعير", icon: "🌾" },
  { code: "potato", nameAr: "بطاطا", icon: "🥔" },
  { code: "tomato", nameAr: "طماطم", icon: "🍅" },
  { code: "olive", nameAr: "زيتون", icon: "🫒" },
  { code: "date", nameAr: "تمر", icon: "🌴" },
  { code: "onion", nameAr: "بصل", icon: "🧅" },
];

const analysisTypes = [
  { code: "detailed", nameAr: "تحليل شامل", icon: "📋", desc: "تحليل كامل مع التكاليف والمخاطر" },
  { code: "yield", nameAr: "تقدير الإنتاج", icon: "📊", desc: "توقع الكمية والعائد" },
  { code: "irrigation", nameAr: "الري الذكي", icon: "💧", desc: "متى وكم تسقي" },
  { code: "harvest", nameAr: "توقيت الحصاد", icon: "🌾", desc: "أفضل وقت للحصاد" },
  { code: "scenarios", nameAr: "ماذا لو؟", icon: "🔮", desc: "محاكاة السيناريوهات" },
];

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnalysisData = Record<string, any>;

export default function AdvancedIntelligencePage() {
  const [selectedCrop, setSelectedCrop] = useState("wheat");
  const [plotArea, setPlotArea] = useState("1");
  const [irrigationType, setIrrigationType] = useState("drip");
  const [soilType, setSoilType] = useState("loamy");
  const [plantDate, setPlantDate] = useState("");
  const [growthStage, setGrowthStage] = useState("vegetative");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ type: string; data: AnalysisData } | null>(null);
  const [activeAnalysis, setActiveAnalysis] = useState("detailed");
  const [wilayaCode, setWilayaCode] = useState("17");
  const [selectedScenarios, setSelectedScenarios] = useState<string[]>(["drought", "pest_outbreak", "market_crash"]);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [budget, setBudget] = useState("");
  const [fertilizerUsed, setFertilizerUsed] = useState(true);
  const [pestControl, setPestControl] = useState(true);

  useEffect(() => {
    const farmerData = localStorage.getItem("agriwise_farmer");
    if (farmerData) {
      try {
        const farmer = JSON.parse(farmerData);
        if (farmer.wilaya) setWilayaCode(farmer.wilaya);
      } catch {}
    }
    const defaultDate = new Date();
    defaultDate.setDate(defaultDate.getDate() - 60);
    setPlantDate(defaultDate.toISOString().split("T")[0]);
  }, []);

  const runAnalysis = async () => {
    setLoading(true);
    setResult(null);

    try {
      const response = await fetch("/api/agribrain", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          type: activeAnalysis,
          data: {
            cropCode: selectedCrop,
            plotArea: parseFloat(plotArea) || 1,
            wilayaCode,
            irrigationType,
            soilType,
            plantDate,
            growthStage,
            fertilizerUsed,
            pestControlApplied: pestControl,
            budget: budget ? parseInt(budget) : undefined,
            selectedScenarios,
            weather: { temperature: 25, humidity: 50, windSpeed: 10, precipitation: 0 },
            weatherForecast: [
              { date: new Date().toISOString(), tempMax: 28, tempMin: 15, precipitationProbability: 10 },
              { date: new Date(Date.now() + 86400000).toISOString(), tempMax: 30, tempMin: 16, precipitationProbability: 5 },
              { date: new Date(Date.now() + 172800000).toISOString(), tempMax: 27, tempMin: 14, precipitationProbability: 30 },
            ],
          },
        }),
      });

      const data = await response.json();
      if (data.success) {
        setResult({ type: activeAnalysis, data: data.data });
      }
    } catch (error) {
      console.error("Analysis error:", error);
    } finally {
      setLoading(false);
    }
  };

  const formatNumber = (num: number) => new Intl.NumberFormat("ar-DZ").format(num);
  const formatCurrency = (num: number) => `${formatNumber(num)} دج`;

  const toggleScenario = (code: string) => {
    setSelectedScenarios(prev => 
      prev.includes(code) ? prev.filter(s => s !== code) : [...prev, code]
    );
  };

  const scenarios = [
    { code: "drought", nameAr: "جفاف", icon: "🏜️", cat: "weather" },
    { code: "heavy_rain", nameAr: "أمطار غزيرة", icon: "🌧️", cat: "weather" },
    { code: "frost", nameAr: "صقيع", icon: "❄️", cat: "weather" },
    { code: "heatwave", nameAr: "موجة حر", icon: "🥵", cat: "weather" },
    { code: "pest_outbreak", nameAr: "آفات", icon: "🐛", cat: "biological" },
    { code: "market_crash", nameAr: "انهيار أسعار", icon: "📉", cat: "market" },
    { code: "market_boom", nameAr: "ارتفاع أسعار", icon: "📈", cat: "market" },
    { code: "no_fertilizer", nameAr: "بدون تسميد", icon: "🌱", cat: "input" },
    { code: "organic_only", nameAr: "عضوي فقط", icon: "🌿", cat: "input" },
  ];

  return (
    <main className="page">
      {/* Header */}
      <header className="page-header">
        <h1 className="page-title">🧠 الذكاء الزراعي المتقدم</h1>
        <p className="page-subtitle">تحليلات شاملة بالذكاء الاصطناعي</p>
      </header>

      {/* Analysis Type Selection */}
      <div style={{ marginBottom: "1.5rem", overflowX: "auto" }}>
        <div style={{ display: "flex", gap: "0.5rem", minWidth: "max-content", paddingBottom: "0.5rem" }}>
          {analysisTypes.map((type) => (
            <button
              key={type.code}
              onClick={() => { setActiveAnalysis(type.code); setResult(null); }}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                padding: "0.75rem 1rem",
                borderRadius: "var(--radius-lg)",
                border: activeAnalysis === type.code ? "2px solid var(--color-primary-500)" : "1px solid var(--background-tertiary)",
                background: activeAnalysis === type.code ? "rgba(34, 197, 94, 0.1)" : "var(--background-secondary)",
                cursor: "pointer",
                minWidth: "90px",
              }}
            >
              <span style={{ fontSize: "1.5rem" }}>{type.icon}</span>
              <span style={{ fontSize: "0.8rem", fontWeight: 600, marginTop: "0.25rem" }}>{type.nameAr}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Input Form */}
      <div className="card fade-in" style={{ marginBottom: "1.5rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
          <h3 style={{ margin: 0, fontSize: "1rem" }}>⚙️ البيانات</h3>
          <button
            className="btn btn-secondary"
            style={{ padding: "0.4rem 0.75rem", fontSize: "0.8rem" }}
            onClick={() => setShowAdvanced(!showAdvanced)}
          >
            {showAdvanced ? "إخفاء المتقدم" : "خيارات متقدمة"}
          </button>
        </div>
        
        {/* Crop Selection */}
        <div className="input-group">
          <label className="input-label">المحصول</label>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
            {crops.map((crop) => (
              <button
                key={crop.code}
                className={`btn ${selectedCrop === crop.code ? "btn-primary" : "btn-secondary"}`}
                onClick={() => setSelectedCrop(crop.code)}
                style={{ padding: "0.5rem 0.75rem", fontSize: "0.85rem" }}
              >
                {crop.icon} {crop.nameAr}
              </button>
            ))}
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
          <div className="input-group">
            <label className="input-label">المساحة (هكتار)</label>
            <input type="number" className="input" value={plotArea} onChange={(e) => setPlotArea(e.target.value)} min="0.1" step="0.1" />
          </div>
          <div className="input-group">
            <label className="input-label">تاريخ الزراعة</label>
            <input type="date" className="input" value={plantDate} onChange={(e) => setPlantDate(e.target.value)} />
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
          <div className="input-group">
            <label className="input-label">نوع الري</label>
            <select className="input" value={irrigationType} onChange={(e) => setIrrigationType(e.target.value)}>
              <option value="drip">تنقيط</option>
              <option value="pivot">محوري</option>
              <option value="sprinkler">رش</option>
              <option value="flood">غمر</option>
              <option value="rainfed">بعلي</option>
            </select>
          </div>
          <div className="input-group">
            <label className="input-label">نوع التربة</label>
            <select className="input" value={soilType} onChange={(e) => setSoilType(e.target.value)}>
              <option value="loamy">طينية صفراء</option>
              <option value="clay">طينية</option>
              <option value="sandy">رملية</option>
              <option value="rocky">صخرية</option>
            </select>
          </div>
        </div>

        {/* Advanced Options */}
        {showAdvanced && (
          <div className="fade-in" style={{ marginTop: "1rem", padding: "1rem", background: "var(--background-secondary)", borderRadius: "var(--radius-lg)" }}>
            <h4 style={{ margin: "0 0 1rem 0", fontSize: "0.9rem" }}>🔧 خيارات متقدمة</h4>
            
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
              <div className="input-group">
                <label className="input-label">مرحلة النمو</label>
                <select className="input" value={growthStage} onChange={(e) => setGrowthStage(e.target.value)}>
                  <option value="seedling">شتلة</option>
                  <option value="vegetative">نمو خضري</option>
                  <option value="flowering">إزهار</option>
                  <option value="fruiting">إثمار</option>
                  <option value="mature">نضج</option>
                </select>
              </div>
              <div className="input-group">
                <label className="input-label">الميزانية (دج)</label>
                <input type="number" className="input" value={budget} onChange={(e) => setBudget(e.target.value)} placeholder="اختياري" />
              </div>
            </div>

            <div style={{ display: "flex", gap: "1rem", marginTop: "1rem" }}>
              <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
                <input type="checkbox" checked={fertilizerUsed} onChange={(e) => setFertilizerUsed(e.target.checked)} />
                <span>استخدام الأسمدة</span>
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
                <input type="checkbox" checked={pestControl} onChange={(e) => setPestControl(e.target.checked)} />
                <span>مكافحة الآفات</span>
              </label>
            </div>
          </div>
        )}

        {/* Scenario Selection (for scenarios type) */}
        {activeAnalysis === "scenarios" && (
          <div className="input-group" style={{ marginTop: "1rem" }}>
            <label className="input-label">اختر السيناريوهات للمحاكاة</label>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
              {scenarios.map((s) => (
                <button
                  key={s.code}
                  onClick={() => toggleScenario(s.code)}
                  style={{
                    padding: "0.5rem 0.75rem",
                    borderRadius: "var(--radius-lg)",
                    border: selectedScenarios.includes(s.code) ? "2px solid var(--color-primary-500)" : "1px solid var(--background-tertiary)",
                    background: selectedScenarios.includes(s.code) ? "rgba(34, 197, 94, 0.1)" : "var(--background-secondary)",
                    cursor: "pointer",
                    fontSize: "0.85rem",
                  }}
                >
                  {s.icon} {s.nameAr}
                </button>
              ))}
            </div>
          </div>
        )}

        <button className="btn btn-primary" onClick={runAnalysis} disabled={loading} style={{ width: "100%", marginTop: "1rem" }}>
          {loading ? <div className="spinner" style={{ width: "20px", height: "20px" }} /> : <>🔍 تحليل بالذكاء الاصطناعي</>}
        </button>
      </div>

      {/* Results */}
      {result && (
        <div className="fade-in">
          {/* Detailed Analysis Results */}
          {result.type === "detailed" && result.data && (
            <>
              {/* Crop Info & Suitability */}
              <div className="card" style={{ marginBottom: "1rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div>
                    <h3 style={{ margin: 0 }}>{result.data.cropInfo?.nameAr || selectedCrop}</h3>
                    <p style={{ margin: "0.25rem 0 0 0", fontSize: "0.8rem", color: "var(--foreground-muted)", fontStyle: "italic" }}>
                      {result.data.cropInfo?.scientificName}
                    </p>
                  </div>
                  <div style={{ 
                    width: "60px", 
                    height: "60px", 
                    borderRadius: "50%",
                    background: `conic-gradient(var(--color-primary-500) ${result.data.suitability?.overall || 0}%, var(--background-tertiary) 0)`,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}>
                    <div style={{ 
                      width: "50px", 
                      height: "50px", 
                      borderRadius: "50%", 
                      background: "var(--background-primary)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontWeight: 700,
                    }}>
                      {result.data.suitability?.overall || 0}%
                    </div>
                  </div>
                </div>
                
                <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "0.5rem", marginTop: "1rem" }}>
                  {[
                    { label: "المناخ", value: result.data.suitability?.climate },
                    { label: "التربة", value: result.data.suitability?.soil },
                    { label: "المياه", value: result.data.suitability?.water },
                    { label: "السوق", value: result.data.suitability?.market },
                  ].map((item, i) => (
                    <div key={i} style={{ textAlign: "center", padding: "0.5rem", background: "var(--background-secondary)", borderRadius: "var(--radius-md)" }}>
                      <div style={{ fontSize: "1rem", fontWeight: 600 }}>{item.value}%</div>
                      <div style={{ fontSize: "0.7rem", color: "var(--foreground-muted)" }}>{item.label}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Financial Summary */}
              {result.data.financials && (
                <div className="card" style={{ marginBottom: "1rem" }}>
                  <h4 style={{ margin: "0 0 1rem 0" }}>💰 التحليل المالي</h4>
                  
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.75rem", marginBottom: "1rem" }}>
                    <div style={{ textAlign: "center", padding: "1rem", background: "rgba(239, 68, 68, 0.1)", borderRadius: "var(--radius-lg)" }}>
                      <div style={{ fontSize: "1.25rem", fontWeight: 700, color: "var(--color-error-500)" }}>
                        {formatCurrency(result.data.financials.estimatedCosts?.total || 0)}
                      </div>
                      <div style={{ fontSize: "0.75rem" }}>إجمالي التكاليف</div>
                    </div>
                    <div style={{ textAlign: "center", padding: "1rem", background: "rgba(34, 197, 94, 0.1)", borderRadius: "var(--radius-lg)" }}>
                      <div style={{ fontSize: "1.25rem", fontWeight: 700, color: "var(--color-primary-500)" }}>
                        {formatCurrency(result.data.financials.estimatedRevenue?.maxRevenue || 0)}
                      </div>
                      <div style={{ fontSize: "0.75rem" }}>أقصى عائد</div>
                    </div>
                    <div style={{ textAlign: "center", padding: "1rem", background: "rgba(59, 130, 246, 0.1)", borderRadius: "var(--radius-lg)" }}>
                      <div style={{ fontSize: "1.25rem", fontWeight: 700, color: "#3b82f6" }}>
                        {result.data.financials.roi}%
                      </div>
                      <div style={{ fontSize: "0.75rem" }}>العائد على الاستثمار</div>
                    </div>
                  </div>

                  <div style={{ fontSize: "0.85rem" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", padding: "0.5rem 0", borderBottom: "1px solid var(--background-tertiary)" }}>
                      <span>البذور</span><span>{formatCurrency(result.data.financials.estimatedCosts?.seeds || 0)}</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", padding: "0.5rem 0", borderBottom: "1px solid var(--background-tertiary)" }}>
                      <span>الأسمدة</span><span>{formatCurrency(result.data.financials.estimatedCosts?.fertilizers || 0)}</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", padding: "0.5rem 0", borderBottom: "1px solid var(--background-tertiary)" }}>
                      <span>المبيدات</span><span>{formatCurrency(result.data.financials.estimatedCosts?.pesticides || 0)}</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", padding: "0.5rem 0", borderBottom: "1px solid var(--background-tertiary)" }}>
                      <span>الري</span><span>{formatCurrency(result.data.financials.estimatedCosts?.irrigation || 0)}</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", padding: "0.5rem 0" }}>
                      <span>العمالة والمعدات</span><span>{formatCurrency((result.data.financials.estimatedCosts?.labor || 0) + (result.data.financials.estimatedCosts?.equipment || 0))}</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Growth Timeline */}
              {result.data.timeline && result.data.timeline.length > 0 && (
                <div className="card" style={{ marginBottom: "1rem" }}>
                  <h4 style={{ margin: "0 0 1rem 0" }}>📅 جدول النمو</h4>
                  <div style={{ position: "relative" }}>
                    {result.data.timeline.map((phase: { phaseAr: string; startDay: number; endDay: number; tasks: Array<{ nameAr: string; critical: boolean }> }, i: number) => (
                      <div key={i} style={{ 
                        display: "flex", 
                        gap: "1rem", 
                        marginBottom: "1rem",
                        paddingRight: "1.5rem",
                        borderRight: "2px solid var(--color-primary-500)",
                        position: "relative",
                      }}>
                        <div style={{
                          position: "absolute",
                          right: "-7px",
                          top: "0",
                          width: "12px",
                          height: "12px",
                          borderRadius: "50%",
                          background: "var(--color-primary-500)",
                        }} />
                        <div style={{ flex: 1 }}>
                          <div style={{ fontWeight: 600 }}>{phase.phaseAr}</div>
                          <div style={{ fontSize: "0.75rem", color: "var(--foreground-muted)" }}>
                            يوم {phase.startDay} - {phase.endDay}
                          </div>
                          <div style={{ marginTop: "0.5rem", fontSize: "0.85rem" }}>
                            {phase.tasks?.slice(0, 2).map((task: { nameAr: string; critical: boolean }, j: number) => (
                              <span key={j} style={{ 
                                display: "inline-block",
                                margin: "0.15rem",
                                padding: "0.2rem 0.5rem",
                                background: task.critical ? "rgba(239, 68, 68, 0.1)" : "var(--background-secondary)",
                                borderRadius: "var(--radius-sm)",
                                fontSize: "0.75rem",
                              }}>
                                {task.critical && "⚠️ "}{task.nameAr}
                              </span>
                            ))}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Risks */}
              {result.data.risks && result.data.risks.length > 0 && (
                <div className="card" style={{ marginBottom: "1rem" }}>
                  <h4 style={{ margin: "0 0 1rem 0" }}>⚠️ تحليل المخاطر</h4>
                  {result.data.risks.map((risk: { typeAr: string; probability: string; impact: string; descriptionAr: string; preventionAr: string }, i: number) => (
                    <div key={i} style={{ 
                      padding: "0.75rem", 
                      marginBottom: "0.5rem",
                      background: risk.probability === "high" ? "rgba(239, 68, 68, 0.1)" : "var(--background-secondary)", 
                      borderRadius: "var(--radius-md)",
                    }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span style={{ fontWeight: 600 }}>{risk.typeAr}</span>
                        <span style={{ 
                          fontSize: "0.7rem", 
                          padding: "0.2rem 0.5rem",
                          borderRadius: "var(--radius-full)",
                          background: risk.probability === "high" ? "var(--color-error-500)" : risk.probability === "medium" ? "var(--color-warning-500)" : "var(--color-primary-500)",
                          color: "white",
                        }}>
                          {risk.probability === "high" ? "مرتفع" : risk.probability === "medium" ? "متوسط" : "منخفض"}
                        </span>
                      </div>
                      <p style={{ margin: "0.5rem 0 0 0", fontSize: "0.85rem", color: "var(--foreground-muted)" }}>
                        {risk.descriptionAr}
                      </p>
                      <p style={{ margin: "0.25rem 0 0 0", fontSize: "0.8rem" }}>
                        💡 {risk.preventionAr}
                      </p>
                    </div>
                  ))}
                </div>
              )}

              {/* Optimizations */}
              {result.data.optimizations && result.data.optimizations.length > 0 && (
                <div className="card" style={{ marginBottom: "1rem" }}>
                  <h4 style={{ margin: "0 0 1rem 0" }}>🚀 فرص التحسين</h4>
                  {result.data.optimizations.map((opt: { titleAr: string; descriptionAr: string; impact: string; difficulty: string; investmentNeeded: number }, i: number) => (
                    <div key={i} style={{ 
                      padding: "0.75rem", 
                      marginBottom: "0.5rem",
                      background: "var(--background-secondary)", 
                      borderRadius: "var(--radius-md)",
                      borderRight: "3px solid var(--color-primary-500)",
                    }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span style={{ fontWeight: 600 }}>{opt.titleAr}</span>
                        <span style={{ fontSize: "0.85rem", color: "var(--color-primary-500)", fontWeight: 600 }}>{opt.impact}</span>
                      </div>
                      <p style={{ margin: "0.5rem 0", fontSize: "0.85rem", color: "var(--foreground-muted)" }}>
                        {opt.descriptionAr}
                      </p>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem" }}>
                        <span>صعوبة: {opt.difficulty === "easy" ? "سهل" : opt.difficulty === "medium" ? "متوسط" : "صعب"}</span>
                        <span>استثمار: {formatCurrency(opt.investmentNeeded)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {/* Scenarios Results */}
          {result.type === "scenarios" && result.data?.scenarios && (
            <div className="card" style={{ marginBottom: "1rem" }}>
              <h3 style={{ margin: "0 0 1rem 0" }}>🔮 نتائج المحاكاة</h3>
              {result.data.scenarios.map((scenario: { nameAr: string; descriptionAr: string; yieldImpact: number; revenueImpact: number; riskLevel: string; mitigationsAr: string[]; probabilityThisSeason: number }, i: number) => (
                <div key={i} style={{ 
                  padding: "1rem", 
                  marginBottom: "0.75rem",
                  background: "var(--background-secondary)", 
                  borderRadius: "var(--radius-lg)",
                  borderRight: `4px solid ${scenario.riskLevel === "critical" ? "var(--color-error-500)" : scenario.riskLevel === "high" ? "var(--color-warning-500)" : "var(--color-primary-500)"}`,
                }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                    <div>
                      <h4 style={{ margin: 0 }}>{scenario.nameAr}</h4>
                      <p style={{ margin: "0.25rem 0 0 0", fontSize: "0.85rem", color: "var(--foreground-muted)" }}>{scenario.descriptionAr}</p>
                    </div>
                    <span style={{ 
                      padding: "0.2rem 0.5rem",
                      borderRadius: "var(--radius-full)",
                      fontSize: "0.7rem",
                      background: "var(--background-tertiary)",
                    }}>
                      احتمال: {scenario.probabilityThisSeason}%
                    </span>
                  </div>
                  
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem", marginTop: "0.75rem" }}>
                    <div style={{ padding: "0.5rem", background: "var(--background-primary)", borderRadius: "var(--radius-md)", textAlign: "center" }}>
                      <div style={{ fontSize: "1.25rem", fontWeight: 700, color: scenario.yieldImpact >= 0 ? "var(--color-primary-500)" : "var(--color-error-500)" }}>
                        {scenario.yieldImpact >= 0 ? "+" : ""}{scenario.yieldImpact}%
                      </div>
                      <div style={{ fontSize: "0.7rem" }}>تأثير الإنتاج</div>
                    </div>
                    <div style={{ padding: "0.5rem", background: "var(--background-primary)", borderRadius: "var(--radius-md)", textAlign: "center" }}>
                      <div style={{ fontSize: "1.25rem", fontWeight: 700, color: scenario.revenueImpact >= 0 ? "var(--color-primary-500)" : "var(--color-error-500)" }}>
                        {scenario.revenueImpact >= 0 ? "+" : ""}{scenario.revenueImpact}%
                      </div>
                      <div style={{ fontSize: "0.7rem" }}>تأثير الإيراد</div>
                    </div>
                  </div>

                  {scenario.mitigationsAr && scenario.mitigationsAr.length > 0 && (
                    <div style={{ marginTop: "0.75rem" }}>
                      <div style={{ fontSize: "0.8rem", fontWeight: 600, marginBottom: "0.25rem" }}>🛡️ إجراءات وقائية:</div>
                      <ul style={{ margin: 0, paddingRight: "1.25rem", fontSize: "0.8rem" }}>
                        {scenario.mitigationsAr.slice(0, 3).map((m: string, j: number) => (
                          <li key={j}>{m}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Yield/Irrigation/Harvest Results - Same as before but with better styling */}
          {(result.type === "yield" || result.type === "irrigation" || result.type === "harvest") && (
            <div className="card" style={{ marginBottom: "1rem", padding: "1.5rem" }}>
              <pre style={{ margin: 0, fontSize: "0.8rem", whiteSpace: "pre-wrap", direction: "ltr" }}>
                {JSON.stringify(result.data, null, 2)}
              </pre>
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

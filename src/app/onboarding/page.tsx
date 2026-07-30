"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import wilayasData from "@/data/algeria/wilayas.json";

type Step = "phone" | "info" | "farm" | "complete";

interface FarmerData {
  phone: string;
  name: string;
  wilaya: string;
  wilayaName: string;
  commune: string;
  farmName: string;
  farmArea: string;
}

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("phone");
  const [isLoading, setIsLoading] = useState(false);
  const [formData, setFormData] = useState<FarmerData>({
    phone: "",
    name: "",
    wilaya: "",
    wilayaName: "",
    commune: "",
    farmName: "",
    farmArea: "",
  });

  const steps: Step[] = ["phone", "info", "farm", "complete"];
  const currentStepIndex = steps.indexOf(step);

  const handlePhoneSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (formData.phone.length < 10) return;
    
    setIsLoading(true);
    // Simulate OTP verification
    await new Promise(resolve => setTimeout(resolve, 1000));
    setIsLoading(false);
    setStep("info");
  };

  const handleInfoSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name || !formData.wilaya) return;
    setStep("farm");
  };

  const handleFarmSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    
    // Save farmer data
    localStorage.setItem("agriwise_farmer", JSON.stringify(formData));
    
    await new Promise(resolve => setTimeout(resolve, 500));
    setIsLoading(false);
    setStep("complete");
  };

  const handleComplete = () => {
    router.push("/");
  };

  const handleWilayaChange = (code: string) => {
    const wilaya = wilayasData.wilayas.find(w => w.code === code);
    setFormData({
      ...formData,
      wilaya: code,
      wilayaName: wilaya?.nameAr || "",
    });
  };

  return (
    <main className="page" style={{ display: "flex", flexDirection: "column", minHeight: "100vh" }}>
      {/* Progress Steps */}
      <div className="progress-steps">
        {steps.slice(0, -1).map((s, i) => (
          <div key={s} style={{ display: "flex", alignItems: "center" }}>
            <div className={`progress-step ${i < currentStepIndex ? "completed" : ""} ${i === currentStepIndex ? "active" : ""}`}>
              {i < currentStepIndex ? "✓" : i + 1}
            </div>
            {i < steps.length - 2 && (
              <div className={`progress-line ${i < currentStepIndex ? "completed" : ""}`} />
            )}
          </div>
        ))}
      </div>

      {/* Step Content */}
      <div className="fade-in" style={{ flex: 1, display: "flex", flexDirection: "column" }}>
        
        {/* Phone Verification */}
        {step === "phone" && (
          <form onSubmit={handlePhoneSubmit} style={{ flex: 1, display: "flex", flexDirection: "column" }}>
            <div style={{ textAlign: "center", marginBottom: "2rem" }}>
              <div style={{ fontSize: "4rem", marginBottom: "1rem" }}>📱</div>
              <h1 style={{ fontSize: "1.5rem", marginBottom: "0.5rem" }}>مرحباً بك!</h1>
              <p style={{ color: "var(--foreground-muted)" }}>أدخل رقم هاتفك للبدء</p>
            </div>

            <div className="input-group">
              <label className="input-label">رقم الهاتف</label>
              <input
                type="tel"
                className="input"
                placeholder="0555 00 00 00"
                value={formData.phone}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value.replace(/\D/g, "") })}
                style={{ direction: "ltr", textAlign: "left", fontSize: "1.25rem", letterSpacing: "2px" }}
                maxLength={10}
              />
            </div>

            <div style={{ marginTop: "auto" }}>
              <button 
                type="submit" 
                className="btn btn-primary" 
                style={{ width: "100%" }}
                disabled={formData.phone.length < 10 || isLoading}
              >
                {isLoading ? (
                  <div className="spinner" style={{ width: "24px", height: "24px" }} />
                ) : (
                  "التالي"
                )}
              </button>
            </div>
          </form>
        )}

        {/* Farmer Info */}
        {step === "info" && (
          <form onSubmit={handleInfoSubmit} style={{ flex: 1, display: "flex", flexDirection: "column" }}>
            <div style={{ textAlign: "center", marginBottom: "2rem" }}>
              <div style={{ fontSize: "4rem", marginBottom: "1rem" }}>👤</div>
              <h1 style={{ fontSize: "1.5rem", marginBottom: "0.5rem" }}>معلوماتك</h1>
              <p style={{ color: "var(--foreground-muted)" }}>ساعدنا نتعرف عليك</p>
            </div>

            <div className="input-group">
              <label className="input-label">الاسم الكامل</label>
              <input
                type="text"
                className="input"
                placeholder="محمد بن علي"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              />
            </div>

            <div className="input-group">
              <label className="input-label">الولاية</label>
              <select
                className="input select"
                value={formData.wilaya}
                onChange={(e) => handleWilayaChange(e.target.value)}
              >
                <option value="">اختر الولاية</option>
                {wilayasData.wilayas.map((w) => (
                  <option key={w.code} value={w.code}>
                    {w.code} - {w.nameAr}
                  </option>
                ))}
              </select>
            </div>

            <div className="input-group">
              <label className="input-label">البلدية (اختياري)</label>
              <input
                type="text"
                className="input"
                placeholder="اسم البلدية"
                value={formData.commune}
                onChange={(e) => setFormData({ ...formData, commune: e.target.value })}
              />
            </div>

            <div style={{ marginTop: "auto", display: "flex", gap: "1rem" }}>
              <button 
                type="button" 
                className="btn btn-secondary"
                onClick={() => setStep("phone")}
                style={{ flex: 1 }}
              >
                رجوع
              </button>
              <button 
                type="submit" 
                className="btn btn-primary"
                disabled={!formData.name || !formData.wilaya}
                style={{ flex: 2 }}
              >
                التالي
              </button>
            </div>
          </form>
        )}

        {/* Farm Setup */}
        {step === "farm" && (
          <form onSubmit={handleFarmSubmit} style={{ flex: 1, display: "flex", flexDirection: "column" }}>
            <div style={{ textAlign: "center", marginBottom: "2rem" }}>
              <div style={{ fontSize: "4rem", marginBottom: "1rem" }}>🚜</div>
              <h1 style={{ fontSize: "1.5rem", marginBottom: "0.5rem" }}>مزرعتك الأولى</h1>
              <p style={{ color: "var(--foreground-muted)" }}>أضف معلومات مزرعتك</p>
            </div>

            <div className="input-group">
              <label className="input-label">اسم المزرعة</label>
              <input
                type="text"
                className="input"
                placeholder="مزرعة الأمل"
                value={formData.farmName}
                onChange={(e) => setFormData({ ...formData, farmName: e.target.value })}
              />
            </div>

            <div className="input-group">
              <label className="input-label">المساحة الإجمالية (هكتار)</label>
              <input
                type="number"
                className="input"
                placeholder="10"
                value={formData.farmArea}
                onChange={(e) => setFormData({ ...formData, farmArea: e.target.value })}
                style={{ direction: "ltr", textAlign: "left" }}
                min="0"
                step="0.1"
              />
            </div>

            <div className="alert alert-success" style={{ marginTop: "1rem" }}>
              <span style={{ fontSize: "1.5rem" }}>💡</span>
              <div>
                <p style={{ margin: 0, fontSize: "0.9rem" }}>
                  يمكنك إضافة المزيد من المزارع والقطع لاحقاً من إعدادات حسابك.
                </p>
              </div>
            </div>

            <div style={{ marginTop: "auto", display: "flex", gap: "1rem" }}>
              <button 
                type="button" 
                className="btn btn-secondary"
                onClick={() => setStep("info")}
                style={{ flex: 1 }}
              >
                رجوع
              </button>
              <button 
                type="submit" 
                className="btn btn-primary"
                disabled={!formData.farmName || isLoading}
                style={{ flex: 2 }}
              >
                {isLoading ? (
                  <div className="spinner" style={{ width: "24px", height: "24px" }} />
                ) : (
                  "إنهاء التسجيل"
                )}
              </button>
            </div>
          </form>
        )}

        {/* Complete */}
        {step === "complete" && (
          <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center", textAlign: "center" }}>
            <div style={{ fontSize: "5rem", marginBottom: "1.5rem" }}>🎉</div>
            <h1 style={{ fontSize: "1.75rem", marginBottom: "0.5rem", color: "var(--color-primary-500)" }}>
              مبروك!
            </h1>
            <p style={{ color: "var(--foreground-muted)", marginBottom: "0.5rem" }}>
              تم إنشاء حسابك بنجاح
            </p>
            <p style={{ color: "var(--foreground-muted)", fontSize: "0.9rem", marginBottom: "2rem" }}>
              {formData.name} - {formData.wilayaName}
            </p>

            <div className="card" style={{ marginBottom: "2rem", textAlign: "right" }}>
              <h3 style={{ margin: "0 0 1rem 0", fontSize: "1rem" }}>✨ يمكنك الآن:</h3>
              <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
                <li style={{ padding: "0.5rem 0", borderBottom: "1px solid var(--background-tertiary)" }}>📅 إضافة محاصيلك وتتبع مواعيدها</li>
                <li style={{ padding: "0.5rem 0", borderBottom: "1px solid var(--background-tertiary)" }}>🌤️ متابعة توقعات الطقس</li>
                <li style={{ padding: "0.5rem 0", borderBottom: "1px solid var(--background-tertiary)" }}>💡 الحصول على نصائح زراعية</li>
                <li style={{ padding: "0.5rem 0" }}>🚜 إدارة مزارعك وقطعك</li>
              </ul>
            </div>

            <button 
              onClick={handleComplete}
              className="btn btn-primary"
              style={{ width: "100%" }}
            >
              ابدأ استخدام أجري وايز
            </button>
          </div>
        )}
      </div>
    </main>
  );
}

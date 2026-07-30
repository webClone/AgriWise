import cropsData from "@/data/algeria/crops.json";

interface FAOCropDataProps {
  cropCode: string;
  wilayaCode?: string; // To check suitability
}

export default function FAOCropData({ cropCode, wilayaCode }: FAOCropDataProps) {
  const crop = cropsData.crops.find((c) => c.code === cropCode);

  if (!crop) return null;

  const isSuitableRegion = wilayaCode && crop.optimalRegions.includes(wilayaCode);

  return (
    <div className="card fade-in" style={{ marginTop: "1.5rem", border: "1px solid #e5e7eb" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
        <h3 style={{ margin: 0, fontWeight: 600, display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <span style={{ fontSize: "1.5rem" }}>🌐</span>
          بيانات الفاو (FAO Data)
        </h3>
        <span style={{ 
          fontSize: "0.75rem", 
          padding: "0.25rem 0.5rem", 
          background: "#e0f2fe", 
          color: "#0284c7", 
          borderRadius: "99px" 
        }}>
          مرجع زراعي
        </span>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        {/* Description */}
        <div style={{ padding: "0.75rem", background: "var(--background-tertiary)", borderRadius: "8px" }}>
          <p style={{ margin: 0, fontSize: "0.9rem", lineHeight: "1.5" }}>
            {crop.description.ar}
          </p>
        </div>

        {/* Stats Grid */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
          <div style={{ textAlign: "center", padding: "0.75rem", background: "var(--background-secondary)", borderRadius: "8px", border: "1px solid var(--background-tertiary)" }}>
            <div style={{ fontSize: "1.25rem", marginBottom: "0.25rem" }}>⏳</div>
            <div style={{ fontSize: "0.75rem", color: "var(--foreground-muted)" }}>دورة النمو</div>
            <div style={{ fontWeight: 600 }}>{crop.growingDays} يوم</div>
          </div>
          <div style={{ textAlign: "center", padding: "0.75rem", background: "var(--background-secondary)", borderRadius: "8px", border: "1px solid var(--background-tertiary)" }}>
            <div style={{ fontSize: "1.25rem", marginBottom: "0.25rem" }}>💧</div>
            <div style={{ fontSize: "0.75rem", color: "var(--foreground-muted)" }}>احتياج الماء</div>
            <div style={{ fontWeight: 600 }}>
              {crop.waterNeeds === 'high' ? 'عالي' : crop.waterNeeds === 'medium' ? 'متوسط' : 'منخفض'}
            </div>
          </div>
        </div>

        {/* Regional Suitability */}
        {wilayaCode && (
          <div style={{ 
            padding: "0.75rem", 
            borderRadius: "8px", 
            background: isSuitableRegion ? "rgba(34, 197, 94, 0.1)" : "rgba(234, 179, 8, 0.1)",
            color: isSuitableRegion ? "#15803d" : "#a16207",
            border: `1px solid ${isSuitableRegion ? "#bbf7d0" : "#fde047"}`,
            display: "flex",
            alignItems: "center",
            gap: "0.75rem"
          }}>
            <div style={{ fontSize: "1.25rem" }}>{isSuitableRegion ? "✅" : "⚠️"}</div>
            <div>
              <div style={{ fontWeight: 600, fontSize: "0.9rem" }}>
                {isSuitableRegion ? "منطقة ملائمة جداً" : "منطقة خارج النطاق المثالي"}
              </div>
              <div style={{ fontSize: "0.8rem", opacity: 0.9 }}>
                {isSuitableRegion 
                  ? "هذه الولاية مصنفة ضمن المناطق المثالية لزراعة هذا المحصول حسب بيانات الفاو."
                  : "قد يحتاج هذا المحصول لعناية إضافية في منطقتك."}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

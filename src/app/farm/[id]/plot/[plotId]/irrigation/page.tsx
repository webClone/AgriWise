import IrrigationDashboard from "@/components/irrigation/IrrigationDashboard";

export const metadata = {
  title: "Irrigation Control Center | AgriWise",
  description: "Real-time irrigation fleet management, scheduling, and monitoring",
};

export default function IrrigationPage() {
  return (
    <div style={{ padding: "24px 16px", maxWidth: 1100, margin: "0 auto" }}>
      <IrrigationDashboard />
    </div>
  );
}

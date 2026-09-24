import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "AgriWise — Agricultural Intelligence Infrastructure",
  description:
    "AgriWise, powered by AgriBrain, unifies Earth observation, weather, soil, sensors, field evidence, farm operations and economic context into traceable intelligence for agriculture, risk and national food security.",
  keywords: [
    "agricultural intelligence",
    "precision agriculture",
    "AgriBrain",
    "farm management",
    "crop monitoring",
    "satellite agriculture",
    "food security",
    "agricultural risk",
    "AgriWise",
  ],
  openGraph: {
    title: "AgriWise — Agricultural Intelligence Infrastructure",
    description:
      "Where nature's wisdom meets data's precision. Intelligence for every agricultural decision.",
    type: "website",
    siteName: "AgriWise",
  },
};

export default function MarketingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="marketing-root">
      {children}
    </div>
  );
}

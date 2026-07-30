"use client";
import Image from "next/image";
import { useTheme } from "./ThemeProvider";

export function ThemeLogo({ height = 34 }: { height?: number }) {
  const { theme } = useTheme();
  const src = theme === "dark" ? "/logo-dark.png" : "/logo-light.png";
  return (
    <Image
      src={src}
      alt="AgriWise"
      width={Math.round(height * 3.5)}
      height={height}
      style={{ height: `${height}px`, width: "auto", objectFit: "contain" }}
      priority
    />
  );
}

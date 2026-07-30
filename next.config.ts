import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Image optimization
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "services.sentinel-hub.com",
      },
      {
        protocol: "https",
        hostname: "mt1.google.com",
      },
      {
        protocol: "https",
        hostname: "*.onesoil.ai",
      },
    ],
    formats: ["image/avif", "image/webp"],
  },

  // Strict mode disabled due to deck.gl v9 WebGL context double-render bugs
  reactStrictMode: false,
  // Cache invalidation trigger: 1
};

export default nextConfig;

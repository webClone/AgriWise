import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Image optimization
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "**",
      },
    ],
    formats: ["image/avif", "image/webp"],
  },

  // Strict mode disabled due to deck.gl v9 WebGL context double-render bugs
  reactStrictMode: false,
  // Cache invalidation trigger: 1
};

export default nextConfig;

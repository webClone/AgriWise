import { NextRequest, NextResponse } from "next/server";
import {
  isRasterImagePayload,
  transparentRasterTile,
} from "@/lib/raster-tile-response";

/**
 * Esri World Imagery tile proxy.
 * 
 * Fetches tiles server-side from server.arcgisonline.com and returns
 * the image bytes to the browser. This ensures zero direct external
 * browser calls to Esri — all tile traffic goes through our API.
 * 
 * Caching: 24h browser cache + 7 day stale-while-revalidate.
 */
export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ z: string; y: string; x: string }> }
) {
  const { z, y, x } = await params;

  const esriUrl = `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/${z}/${y}/${x}`;

  try {
    const res = await fetch(esriUrl, {
      headers: {
        "User-Agent": "AgriWise/1.0",
      },
      // Next.js fetch cache: revalidate every 24 hours
      next: { revalidate: 86400 },
    });

    if (!res.ok) {
      console.warn(`[Esri Proxy] Upstream returned ${res.status} for ${z}/${y}/${x}`);
      return transparentRasterTile("esri-proxy-fallback", `upstream_http_${res.status}`);
    }

    const buffer = await res.arrayBuffer();
    const contentType = res.headers.get("Content-Type");
    if (!isRasterImagePayload(buffer, contentType)) {
      console.warn(`[Esri Proxy] Upstream returned a non-image tile for ${z}/${y}/${x}`);
      return transparentRasterTile("esri-proxy-fallback", "invalid_upstream_image");
    }

    return new NextResponse(buffer, {
      status: 200,
      headers: {
        "Content-Type": contentType || "image/jpeg",
        "Cache-Control": "public, max-age=86400, stale-while-revalidate=604800",
        "X-Tile-Source": "esri-proxy",
      },
    });
  } catch (error) {
    console.error("[Esri Proxy] Tile fetch failed:", error);
    return transparentRasterTile("esri-proxy-fallback", "network_error");
  }
}

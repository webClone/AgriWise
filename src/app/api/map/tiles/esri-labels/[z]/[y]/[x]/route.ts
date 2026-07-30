import { NextRequest, NextResponse } from "next/server";
import {
  isRasterImagePayload,
  transparentRasterTile,
} from "@/lib/raster-tile-response";

/**
 * Esri World Boundaries/Labels tile proxy.
 * Same pattern as the imagery proxy — zero direct browser-to-Esri calls.
 */
export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ z: string; y: string; x: string }> }
) {
  const { z, y, x } = await params;

  const esriUrl = `https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/${z}/${y}/${x}`;

  try {
    const res = await fetch(esriUrl, {
      headers: { "User-Agent": "AgriWise/1.0" },
      next: { revalidate: 86400 },
    });

    if (!res.ok) {
      console.warn(`[Esri Labels Proxy] Upstream returned ${res.status} for ${z}/${y}/${x}`);
      return transparentRasterTile("esri-labels-proxy-fallback", `upstream_http_${res.status}`);
    }

    const buffer = await res.arrayBuffer();
    const contentType = res.headers.get("Content-Type");
    if (!isRasterImagePayload(buffer, contentType)) {
      console.warn(`[Esri Labels Proxy] Upstream returned a non-image tile for ${z}/${y}/${x}`);
      return transparentRasterTile("esri-labels-proxy-fallback", "invalid_upstream_image");
    }

    return new NextResponse(buffer, {
      status: 200,
      headers: {
        "Content-Type": contentType || "image/png",
        "Cache-Control": "public, max-age=86400, stale-while-revalidate=604800",
        "X-Tile-Source": "esri-labels-proxy",
      },
    });
  } catch (error) {
    console.error("[Esri Labels Proxy] Tile fetch failed:", error);
    return transparentRasterTile("esri-labels-proxy-fallback", "network_error");
  }
}

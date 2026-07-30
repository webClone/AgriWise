/**
 * /api/agribrain/satellite-tile-image/[plotId] — Serves cached satellite tile as PNG
 */
import { NextRequest, NextResponse } from "next/server";
import { authorizePlot } from "@/lib/agribrain/authorize-plot";

const AGRIBRAIN_URL = process.env.AGRIBRAIN_API_URL || "http://127.0.0.1:8000";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ plotId: string }> }
) {
  const { plotId } = await params;
  try {
    const access = await authorizePlot(plotId);
    if (!access.plot) {
      return NextResponse.json(
        { error: access.status === 401 ? "Authentication required" : "Tile not found" },
        { status: access.status },
      );
    }
    const response = await fetch(
      `${AGRIBRAIN_URL}/v2/satellite-tile-image/${encodeURIComponent(plotId)}`,
      {
        headers: { Accept: "image/png" },
        next: { revalidate: 604800 }, // 7-day cache
      }
    );

    if (!response.ok) {
      return NextResponse.json(
        { error: `Tile not found (${response.status})` },
        { status: response.status }
      );
    }

    const imageBuffer = await response.arrayBuffer();

    return new NextResponse(imageBuffer, {
      status: 200,
      headers: {
        "Content-Type": "image/png",
        "Cache-Control": "private, max-age=3600",
        "X-Tile-Source": response.headers.get("X-Tile-Source") || "sentinel-2-l2a",
        "X-Tile-Date": response.headers.get("X-Tile-Date") || "",
      },
    });
  } catch {
    return NextResponse.json({ error: "Failed to fetch tile image" }, { status: 500 });
  }
}

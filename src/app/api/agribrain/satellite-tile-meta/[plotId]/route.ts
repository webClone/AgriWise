/**
 * /api/agribrain/satellite-tile-meta/[plotId] — Satellite tile metadata
 */
import { NextRequest, NextResponse } from "next/server";

const AGRIBRAIN_URL = process.env.AGRIBRAIN_API_URL || "http://127.0.0.1:8000";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ plotId: string }> }
) {
  const { plotId } = await params;
  try {
    const response = await fetch(
      `${AGRIBRAIN_URL}/v2/satellite-tile-meta/${encodeURIComponent(plotId)}`
    );
    const data = await response.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ exists: false, plot_id: plotId }, { status: 500 });
  }
}

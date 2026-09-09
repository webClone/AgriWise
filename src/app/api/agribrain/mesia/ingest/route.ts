import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { getSession } from "@/lib/session";
import { buildSignedInternalHeaders } from "@/lib/agribrain/internal-service-auth";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const session = await getSession();
  const userId = session?.userId || null;
  if (!userId) {
    return NextResponse.json({ error: "Authentication required" }, { status: 401 });
  }

  try {
    const body = await request.json();
    const { plotId, nmeaText } = body;

    if (!plotId || !nmeaText) {
      return NextResponse.json({ error: "plotId and nmeaText are required" }, { status: 400 });
    }

    const authorized = await prisma.plot.findFirst({
      where: {
        id: plotId,
        farm: { userId },
      },
      select: { id: true, farmId: true },
    });

    if (!authorized) {
      return NextResponse.json({ error: "Plot not found or access denied" }, { status: 404 });
    }

    const apiUrl = process.env.AGRIBRAIN_API_URL || "http://127.0.0.1:8000";
    const pathname = "/v2/mesia/ingest-nmea";
    const outboundBody = JSON.stringify({ plot_id: plotId, nmea_text: nmeaText });

    const signedHeaders = buildSignedInternalHeaders(
      "POST",
      pathname,
      {
        tenantId: userId,
        farmId: authorized.farmId,
        plotId,
      },
      outboundBody
    );

    const resp = await fetch(`${apiUrl}${pathname}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...signedHeaders,
      },
      body: outboundBody,
    });

    if (!resp.ok) {
      const err = await resp.text();
      return NextResponse.json({ error: "Failed to ingest NMEA log", details: err }, { status: resp.status });
    }

    const result = await resp.json();
    return NextResponse.json({ success: true, result });
  } catch (err: any) {
    return NextResponse.json({ error: "Server error", details: err?.message }, { status: 500 });
  }
}

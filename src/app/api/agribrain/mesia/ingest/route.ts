import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { getSession } from "@/lib/session";
import { authorizePlot } from "@/lib/agribrain/authorize-plot";
import { buildSignedInternalHeaders } from "@/lib/agribrain/internal-service-auth";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { plotId, nmeaText } = body;

    if (!plotId || !nmeaText) {
      return NextResponse.json({ error: "plotId and nmeaText are required" }, { status: 400 });
    }

    const access = await authorizePlot(plotId);
    if (access.status !== 200 || !access.plot) {
      return NextResponse.json(
        { error: access.status === 401 ? "Authentication required" : "Plot not found or access denied" },
        { status: access.status },
      );
    }

    const authorized = access.plot;
    const tenantId = authorized.farm.userId || access.userId!;

    const apiUrl = process.env.AGRIBRAIN_API_URL || "http://127.0.0.1:8000";
    const pathname = "/v2/mesia/ingest-nmea";
    const outboundBody = JSON.stringify({ plot_id: plotId, nmea_text: nmeaText });

    const signedHeaders = buildSignedInternalHeaders(
      "POST",
      pathname,
      {
        tenantId,
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

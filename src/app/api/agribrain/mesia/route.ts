import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { getSession } from "@/lib/session";
import { buildSignedInternalHeaders } from "@/lib/agribrain/internal-service-auth";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const plotId = searchParams.get("plotId");

  if (!plotId) {
    return NextResponse.json({ error: "plotId is required" }, { status: 400 });
  }

  const session = await getSession();
  const userId = session?.userId || null;
  if (!userId) {
    return NextResponse.json({ error: "Authentication required" }, { status: 401 });
  }

  const authorized = await prisma.plot.findFirst({
    where: {
      id: plotId,
      farm: { userId },
    },
    select: {
      id: true,
      farmId: true,
      geoJson: true,
      soilType: true,
      area: true,
    },
  });

  if (!authorized) {
    return NextResponse.json({ error: "Plot not found or access denied" }, { status: 404 });
  }

  const apiUrl = process.env.AGRIBRAIN_API_URL || "http://127.0.0.1:8000";

  try {
    const pathname = `/v2/mesia/${encodeURIComponent(plotId)}`;
    const bodyObj = {
      geoJson: authorized.geoJson,
      soilType: authorized.soilType,
    };
    const bodyText = JSON.stringify(bodyObj);

    const signedHeaders = buildSignedInternalHeaders(
      "POST",
      pathname,
      {
        tenantId: userId,
        farmId: authorized.farmId,
        plotId,
      },
      bodyText
    );

    const response = await fetch(`${apiUrl}${pathname}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...signedHeaders,
      },
      body: bodyText,
      next: { revalidate: 0 },
    });

    if (!response.ok) {
      const errText = await response.text();
      return NextResponse.json(
        { error: `MESIA backend error: ${response.status}`, details: errText },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json({
      success: true,
      data,
    });
  } catch (err: any) {
    return NextResponse.json(
      { error: "Failed to connect to MESIA service", details: err?.message },
      { status: 502 }
    );
  }
}

export async function POST(request: NextRequest) {
  const session = await getSession();
  const userId = session?.userId || null;
  if (!userId) {
    return NextResponse.json({ error: "Authentication required" }, { status: 401 });
  }

  try {
    const body = await request.json();
    const { action, plotId, ...payload } = body;
    if (!plotId) {
      return NextResponse.json({ error: "plotId is required" }, { status: 400 });
    }

    // Never accept tenant or farm identity from client payload
    delete (payload as any).tenant_id;
    delete (payload as any).tenantId;
    delete (payload as any).farm_id;
    delete (payload as any).farmId;

    const authorized = await prisma.plot.findFirst({
      where: {
        id: plotId,
        farm: { userId },
      },
      select: {
        id: true,
        farmId: true,
      },
    });

    if (!authorized) {
      return NextResponse.json({ error: "Plot not found or access denied" }, { status: 404 });
    }

    const apiUrl = process.env.AGRIBRAIN_API_URL || "http://127.0.0.1:8000";

    if (action === "simulate-wifi-csi") {
      const pathname = "/v2/mesia/simulate-wifi-csi";
      const outboundBody = JSON.stringify({
        plot_id: plotId,
        ap_distance_m: payload.ap_distance_m ?? payload.apDistanceM ?? 35.0,
        ssid: payload.ssid ?? "Farmstead_HQ_IoT",
        frequency_mhz: payload.frequency_mhz ?? payload.frequencyMhz ?? 2437.0,
      });

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

      const response = await fetch(`${apiUrl}${pathname}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...signedHeaders,
        },
        body: outboundBody,
      });

      if (!response.ok) {
        const errText = await response.text();
        return NextResponse.json(
          { error: `MESIA backend error: ${response.status}`, details: errText },
          { status: response.status }
        );
      }

      const data = await response.json();
      return NextResponse.json({ success: true, data });
    }

    if (action === "ingest-nmea") {
      const pathname = "/v2/mesia/ingest-nmea";
      const outboundBody = JSON.stringify({
        plot_id: plotId,
        nmea_text: payload.nmea_text ?? payload.nmeaText ?? "",
      });

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

      const response = await fetch(`${apiUrl}${pathname}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...signedHeaders,
        },
        body: outboundBody,
      });

      if (!response.ok) {
        const errText = await response.text();
        return NextResponse.json(
          { error: `MESIA backend error: ${response.status}`, details: errText },
          { status: response.status }
        );
      }

      const data = await response.json();
      return NextResponse.json({ success: true, data });
    }

    if (action === "ingest-sigmf-csi") {
      const pathname = "/v2/mesia/ingest-sigmf-csi";
      const outboundBody = JSON.stringify({
        plot_id: plotId,
        data_b64: payload.data_b64 ?? payload.dataB64 ?? "",
        meta_json: payload.meta_json ?? payload.metaJson ?? null,
      });

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

      const response = await fetch(`${apiUrl}${pathname}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...signedHeaders,
        },
        body: outboundBody,
      });

      if (!response.ok) {
        const errText = await response.text();
        return NextResponse.json(
          { error: `MESIA backend error: ${response.status}`, details: errText },
          { status: response.status }
        );
      }

      const data = await response.json();
      return NextResponse.json({ success: true, data });
    }

    if (action === "ingest-oran-kpm") {
      const pathname = "/v2/mesia/ingest-oran-kpm";
      const outboundBody = JSON.stringify({
        plot_id: plotId,
        raw_kpm_data: payload.raw_kpm_data ?? payload.rawKpmData ?? {},
        operator_name: payload.operator_name ?? payload.operatorName ?? "Mobilis DZ",
        cell_id: payload.cell_id ?? payload.cellId ?? 60401,
      });

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

      const response = await fetch(`${apiUrl}${pathname}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...signedHeaders,
        },
        body: outboundBody,
      });

      if (!response.ok) {
        const errText = await response.text();
        return NextResponse.json(
          { error: `MESIA backend error: ${response.status}`, details: errText },
          { status: response.status }
        );
      }

      const data = await response.json();
      return NextResponse.json({ success: true, data });
    }

    if (action === "fleet-health") {
      const pathname = `/v2/mesia/${encodeURIComponent(plotId)}/fleet-health`;
      const signedHeaders = buildSignedInternalHeaders(
        "GET",
        pathname,
        {
          tenantId: userId,
          farmId: authorized.farmId,
          plotId,
        }
      );

      const response = await fetch(`${apiUrl}${pathname}`, {
        method: "GET",
        headers: signedHeaders,
        next: { revalidate: 0 },
      });

      if (!response.ok) {
        const errText = await response.text();
        return NextResponse.json(
          { error: `MESIA backend error: ${response.status}`, details: errText },
          { status: response.status }
        );
      }

      const data = await response.json();
      return NextResponse.json({ success: true, data });
    }

    return NextResponse.json({ error: "Unknown action" }, { status: 400 });
  } catch (err: any) {
    return NextResponse.json(
      { error: "Failed to process MESIA action", details: err?.message },
      { status: 500 }
    );
  }
}

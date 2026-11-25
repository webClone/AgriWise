import { NextRequest, NextResponse } from "next/server";
import { authorizePlot } from "@/lib/agribrain/authorize-plot";
import { buildSignedInternalHeaders } from "@/lib/agribrain/internal-service-auth";

export const runtime = "nodejs";

const AGRIBRAIN_URL = process.env.AGRIBRAIN_API_URL || "http://127.0.0.1:8000";

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const plotId = searchParams.get("plotId")?.trim() || "";
    const farmId = searchParams.get("farmId")?.trim() || undefined;
    const asOf = searchParams.get("asOf")?.trim() || "";
    const knowledgeCutoff = searchParams.get("knowledgeCutoff")?.trim() || "";

    if (!plotId) {
      return NextResponse.json(
        { success: false, error: "plotId query parameter is required" },
        { status: 400 },
      );
    }

    const access = await authorizePlot(plotId, farmId);
    if (!access.plot) {
      return NextResponse.json(
        {
          success: false,
          error: access.status === 401 ? "Authentication required" : "Plot not found",
        },
        { status: access.status },
      );
    }

    const tenantId = access.userId || access.plot.farm?.userId;
    if (!tenantId) {
      return NextResponse.json(
        { success: false, error: "Plot tenant owner identity missing" },
        { status: 403 },
      );
    }

    const forwardParams = new URLSearchParams();
    const pairList: Array<[string, string]> = [];
    if (asOf) {
      forwardParams.set("as_of", asOf);
      pairList.push(["as_of", asOf]);
    }
    if (knowledgeCutoff) {
      forwardParams.set("knowledge_cutoff", knowledgeCutoff);
      pairList.push(["knowledge_cutoff", knowledgeCutoff]);
    }

    const targetPath = `/v2/plots/${encodeURIComponent(plotId)}/historical-intelligence`;
    const qs = forwardParams.toString();
    const signedHeaders = buildSignedInternalHeaders(
      "GET",
      targetPath,
      {
        tenantId: tenantId.trim(),
        farmId: access.plot.farmId.trim(),
        plotId: plotId.trim(),
      },
      "",
      pairList,
    );

    const upstream = await fetch(`${AGRIBRAIN_URL}${targetPath}${qs ? `?${qs}` : ""}`, {
      method: "GET",
      headers: {
        ...signedHeaders,
      },
      cache: "no-store",
    });

    if (!upstream.ok) {
      const errText = await upstream.text();
      return NextResponse.json(
        {
          success: false,
          error: `AgriBrain historical-intelligence returned ${upstream.status}`,
          details: errText.slice(0, 300),
        },
        { status: upstream.status },
      );
    }

    const data = await upstream.json();
    return NextResponse.json({ success: true, data }, { status: 200 });
  } catch (error) {
    console.error("[historical-intelligence] GET failed:", error);
    return NextResponse.json(
      {
        success: false,
        error: "Failed to load historical intelligence",
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 },
    );
  }
}

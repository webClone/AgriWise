import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { getSession } from "@/lib/session";
import { authorizePlot } from "@/lib/agribrain/authorize-plot";
import { buildSignedInternalHeaders } from "@/lib/agribrain/internal-service-auth";

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const plotId = searchParams.get("plotId");
  const runId = searchParams.get("runId");

  if (!plotId) {
    return NextResponse.json({ error: "plotId is required" }, { status: 400 });
  }

  const access = await authorizePlot(plotId);
  if (access.status !== 200 || !access.plot) {
    return NextResponse.json(
      { error: access.status === 401 ? "Authentication required" : "Plot not found" },
      { status: access.status },
    );
  }

  const authorized = access.plot;
  const tenantId = authorized.farm.userId || access.userId!;

  const apiUrl = process.env.AGRIBRAIN_API_URL || "http://127.0.0.1:8000";

  try {
    const pathname = `/v2/progress/${encodeURIComponent(plotId)}`;
    const queryParams: Array<[string, string]> = runId ? [["run_id", runId]] : [];
    const queryStr = queryParams.length > 0 ? `?run_id=${encodeURIComponent(runId!)}` : "";

    const signedHeaders = buildSignedInternalHeaders(
      "GET",
      pathname,
      {
        tenantId,
        farmId: authorized.farmId,
        plotId,
      },
      "",
      queryParams
    );

    const progressUrl = `${apiUrl}${pathname}${queryStr}`;
    const response = await fetch(progressUrl, {
      headers: {
        ...signedHeaders,
        "Cache-Control": "no-cache",
      },
      next: { revalidate: 0 },
    });

    if (!response.ok) {
      const errText = await response.text().catch(() => "");
      return NextResponse.json({ error: "Backend error", detail: errText }, { status: response.status });
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error: any) {
    return NextResponse.json({ error: "Failed to fetch progress", detail: error?.message || String(error) }, { status: 500 });
  }
}

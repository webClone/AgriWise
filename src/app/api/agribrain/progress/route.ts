import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { getSession } from "@/lib/session";
import { buildSignedInternalHeaders } from "@/lib/agribrain/internal-service-auth";

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const plotId = searchParams.get("plotId");
  const runId = searchParams.get("runId");

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
    select: { id: true, farmId: true },
  });

  if (!authorized) {
    return NextResponse.json({ error: "Plot not found" }, { status: 404 });
  }

  const apiUrl = process.env.AGRIBRAIN_API_URL || "http://127.0.0.1:8000";

  try {
    const pathname = `/v2/progress/${encodeURIComponent(plotId)}`;
    const queryParams: Array<[string, string]> = runId ? [["run_id", runId]] : [];
    const queryStr = queryParams.length > 0 ? `?run_id=${encodeURIComponent(runId!)}` : "";

    const signedHeaders = buildSignedInternalHeaders(
      "GET",
      pathname,
      {
        tenantId: userId,
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

import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { getSession } from "@/lib/session";

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
    select: { id: true },
  });
  if (!authorized) {
    return NextResponse.json({ error: "Plot not found" }, { status: 404 });
  }

  const apiUrl = process.env.AGRIBRAIN_API_URL || "http://127.0.0.1:8000";

  try {
    const progressUrl = new URL(`${apiUrl}/v2/progress/${plotId}`);
    if (runId) progressUrl.searchParams.set("run_id", runId);
    const response = await fetch(progressUrl, {
      // Don't cache this!
      headers: { "Cache-Control": "no-cache" },
      next: { revalidate: 0 }
    });

    if (!response.ok) {
      return NextResponse.json({ error: "Backend error" }, { status: response.status });
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json({ error: "Failed to fetch progress" }, { status: 500 });
  }
}

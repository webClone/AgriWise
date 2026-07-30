import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { getSession } from "@/lib/session";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ runId: string }> },
) {
  const session = await getSession();
  const userId = session?.userId || null;
  if (!userId) {
    return NextResponse.json({ error: "Authentication required" }, { status: 401 });
  }

  const { runId } = await params;
  const apiUrl = process.env.AGRIBRAIN_API_URL || "http://127.0.0.1:8000";
  const upstream = await fetch(
    `${apiUrl}/v2/runs/${encodeURIComponent(runId)}/result`,
    { cache: "no-store" },
  );
  if (!upstream.ok) {
    return NextResponse.json(
      { error: "Run result not found" },
      { status: upstream.status },
    );
  }

  const envelope = await upstream.json();
  const plotId = String(envelope?.plot_id || "");
  const authorized = await prisma.plot.findFirst({
    where: {
      id: plotId,
      farm: { userId },
    },
    select: { id: true },
  });
  if (!authorized) {
    return NextResponse.json({ error: "Run result not found" }, { status: 404 });
  }
  return NextResponse.json(envelope, {
    headers: { "Cache-Control": "private, no-store" },
  });
}

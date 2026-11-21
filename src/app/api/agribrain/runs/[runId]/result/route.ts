import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { getSession } from "@/lib/session";
import { authorizePlot } from "@/lib/agribrain/authorize-plot";
import { buildSignedInternalHeaders } from "@/lib/agribrain/internal-service-auth";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ runId: string }> },
) {
  const { runId } = await params;
  const notFound = () => NextResponse.json(
    { error: "Run result not found" },
    { status: 404, headers: { "Cache-Control": "private, no-store" } },
  );
  const session = await getSession();
  if (!session?.userId) return notFound();
  if (typeof runId !== "string" || !/^[A-Za-z0-9_.:-]{1,128}$/.test(runId)) {
    return notFound();
  }

  // The authoritative run->namespace binding is created by the authenticated
  // run POST before backend execution. Never infer ownership from an upstream
  // result's plot_id, a client-provided plot_id or a URL identifier.
  const run = await prisma.agriBrainRun.findFirst({
    where: { runId, tenantId: session.userId },
    select: { plotId: true, farmId: true, tenantId: true },
  });
  if (!run) return notFound();
  const access = await authorizePlot(run.plotId, run.farmId);
  if (access.status !== 200 || !access.plot
      || access.plot.id !== run.plotId
      || access.plot.farmId !== run.farmId
      || access.userId !== session.userId) {
    return notFound();
  }

  const apiUrl = process.env.AGRIBRAIN_API_URL || "http://127.0.0.1:8000";
  const pathname = `/v2/runs/${encodeURIComponent(runId)}/result`;
  try {
    const signedHeaders = buildSignedInternalHeaders(
      "GET", pathname,
      { tenantId: session.userId, farmId: run.farmId, plotId: run.plotId },
    );
    const upstream = await fetch(`${apiUrl}${pathname}`, {
      headers: signedHeaders,
      cache: "no-store",
    });
    if (!upstream.ok) return notFound();
    const envelope = await upstream.json();
    if (String(envelope?.plot_id || "") !== run.plotId
        || String(envelope?.run_id || "") !== runId) {
      return notFound();
    }
    return NextResponse.json(envelope, {
      headers: { "Cache-Control": "private, no-store" },
    });
  } catch {
    // Internal network failures must not leak run existence or backend errors.
    return notFound();
  }
}

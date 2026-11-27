import { NextResponse } from "next/server";
import { getSession } from "@/lib/session";
import { buildSignedInternalHeaders } from "@/lib/agribrain/internal-service-auth";

export const runtime = "nodejs";

const AGRIBRAIN_URL = process.env.AGRIBRAIN_API_URL || "http://127.0.0.1:8000";
const BENCHMARK_COHORT_SCOPE = "__benchmark_cohort__";

export async function GET() {
  try {
    const session = await getSession();
    if (!session) {
      return NextResponse.json(
        { success: false, error: "Authentication required" },
        { status: 401 },
      );
    }
    if (session.role !== "ADMIN") {
      return NextResponse.json(
        { success: false, error: "Benchmark admin role required" },
        { status: 403 },
      );
    }

    const benchmarkAdminTenant = (
      process.env.AGRIBRAIN_BENCHMARK_ADMIN_TENANT || "benchmark_admin"
    ).trim();
    const targetPath = "/v2/asmae/benchmark-matrix";
    const signedHeaders = buildSignedInternalHeaders(
      "GET",
      targetPath,
      {
        tenantId: benchmarkAdminTenant,
        farmId: BENCHMARK_COHORT_SCOPE,
        plotId: BENCHMARK_COHORT_SCOPE,
      },
      "",
      "",
    );

    const upstream = await fetch(`${AGRIBRAIN_URL}${targetPath}`, {
      method: "GET",
      headers: {
        ...signedHeaders,
        "X-AgriBrain-Benchmark-Role": "benchmark_admin",
        Accept: "application/json",
      },
      cache: "no-store",
    });

    const data = await upstream.json().catch(() => null);
    if (!upstream.ok) {
      return NextResponse.json(
        {
          success: false,
          error: (data as any)?.detail || `Upstream benchmark error ${upstream.status}`,
        },
        { status: upstream.status },
      );
    }

    return NextResponse.json(data, { status: 200 });
  } catch (err) {
    return NextResponse.json(
      {
        success: false,
        error: err instanceof Error ? err.message : "Failed to fetch benchmark matrix",
      },
      { status: 500 },
    );
  }
}

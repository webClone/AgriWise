import { NextRequest, NextResponse } from "next/server";
import { authenticatedUserId } from "@/lib/tenant-authorization";

const AGRIBRAIN_URL = process.env.AGRIBRAIN_API_URL || "http://127.0.0.1:8000";

export async function POST(request: NextRequest) {
  try {
    if (!(await authenticatedUserId())) {
      return NextResponse.json(
        { success: false, error: "Authentication required" },
        { status: 401 },
      );
    }
    const body = await request.json();
    const { query, history } = body;
    if (typeof query !== "string" || !query.trim() || query.length > 4_000) {
      return NextResponse.json(
        { success: false, error: "query must be a non-empty string of at most 4000 characters" },
        { status: 400 },
      );
    }
    const serializedHistory = history == null ? "" : JSON.stringify(history);
    if (serializedHistory.length > 32_000) {
      return NextResponse.json(
        { success: false, error: "history is too large" },
        { status: 413 },
      );
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10_000);

    const res = await fetch(`${AGRIBRAIN_URL}/v2/intent`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        query: query.trim(),
        history: serializedHistory,
      }),
      signal: controller.signal,
    }).finally(() => clearTimeout(timeoutId));

    if (!res.ok) {
      return NextResponse.json(
        { success: false, error: `Intent service returned ${res.status}` },
        { status: 502 },
      );
    }

    const data = await res.json();
    return NextResponse.json({ success: true, data });
  } catch (error: unknown) {
    console.error("Intent routing error:", error);
    const timedOut = error instanceof Error && error.name === "TimeoutError";
    return NextResponse.json(
      { success: false, error: timedOut ? "Intent service timed out" : "Failed to route intent" },
      { status: timedOut ? 504 : 500 }
    );
  }
}

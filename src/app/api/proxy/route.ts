import { NextRequest, NextResponse } from "next/server";
import { authenticatedUserId } from "@/lib/tenant-authorization";
import { isValidWgs84Point } from "@/lib/agribrain/plot-geometry";

const BACKEND_URL = process.env.AGRIBRAIN_API_URL || "http://127.0.0.1:8000";
const MAX_RESPONSE_BYTES = 5 * 1024 * 1024;

const ENDPOINTS: Record<string, readonly string[]> = {
  "/eo/soil-layers": ["lat", "lng"],
  "/eo/soil-properties": ["lat", "lng"],
  "/eo/environment-analysis": ["lat", "lng"],
  "/eo/land-cover": ["lat", "lng"],
  "/eo/sar-analysis": ["lat", "lng"],
  "/eo/rainfall-climatology": ["lat", "lng"],
  "/eo/rainfall-history": ["lat", "lng", "years"],
  "/eo/drought-analysis": ["lat", "lng"],
  "/eo/rainfall-anomaly": ["lat", "lng"],
  "/eo/water-balance": ["lat", "lng", "days_past", "days_future"],
  "/eo/weather": ["lat", "lng"],
  "/eo/forecast": ["lat", "lng"],
  "/phenology/gdd": ["lat", "lng", "crop", "days"],
  "/phenology/calendar": ["crop"],
  "/phenology/kc": ["crop", "growth_stage"],
};

function boundedInteger(value: string | null, minimum: number, maximum: number): string | null {
  if (value == null || !/^\d+$/.test(value)) return null;
  return String(Math.min(maximum, Math.max(minimum, Number(value))));
}

export async function GET(request: NextRequest) {
  if (!(await authenticatedUserId())) {
    return NextResponse.json({ error: "Authentication required" }, { status: 401 });
  }

  const path = request.nextUrl.searchParams.get("path") || "";
  const allowedKeys = ENDPOINTS[path];
  if (!allowedKeys) {
    return NextResponse.json({ error: "Unsupported data endpoint" }, { status: 404 });
  }

  const upstream = new URL(path, BACKEND_URL);
  for (const key of allowedKeys) {
    const value = request.nextUrl.searchParams.get(key);
    if (value != null) upstream.searchParams.set(key, value);
  }

  if (allowedKeys.includes("lat")) {
    const location = {
      lat: Number(upstream.searchParams.get("lat")),
      lng: Number(upstream.searchParams.get("lng")),
    };
    if (!isValidWgs84Point(location)) {
      return NextResponse.json({ error: "Valid lat and lng are required" }, { status: 400 });
    }
    upstream.searchParams.set("lat", String(location.lat));
    upstream.searchParams.set("lng", String(location.lng));
  }

  for (const key of ["crop", "growth_stage"] as const) {
    const value = upstream.searchParams.get(key);
    if (allowedKeys.includes(key) && (value == null || !/^[A-Za-z0-9_-]{1,64}$/.test(value))) {
      return NextResponse.json({ error: `A valid ${key} is required` }, { status: 400 });
    }
  }
  const numericLimits: Record<string, [number, number]> = {
    years: [1, 50],
    days: [1, 366],
    days_past: [0, 366],
    days_future: [0, 30],
  };
  for (const [key, [minimum, maximum]] of Object.entries(numericLimits)) {
    if (!allowedKeys.includes(key)) continue;
    const value = boundedInteger(upstream.searchParams.get(key), minimum, maximum);
    if (value == null) return NextResponse.json({ error: `A valid ${key} is required` }, { status: 400 });
    upstream.searchParams.set(key, value);
  }

  try {
    const response = await fetch(upstream, { signal: AbortSignal.timeout(20_000) });
    const advertisedLength = Number(response.headers.get("Content-Length"));
    if (Number.isFinite(advertisedLength) && advertisedLength > MAX_RESPONSE_BYTES) {
      return NextResponse.json({ error: "Upstream response is too large" }, { status: 502 });
    }
    const text = await response.text();
    if (Buffer.byteLength(text, "utf8") > MAX_RESPONSE_BYTES) {
      return NextResponse.json({ error: "Upstream response is too large" }, { status: 502 });
    }
    if (!response.ok) {
      return NextResponse.json({ error: `Upstream error: ${response.status}` }, { status: 502 });
    }
    try {
      return NextResponse.json(JSON.parse(text));
    } catch {
      return NextResponse.json({ error: "Upstream returned invalid JSON" }, { status: 502 });
    }
  } catch (error: unknown) {
    const timedOut = error instanceof Error && error.name === "TimeoutError";
    return NextResponse.json(
      { error: timedOut ? "Upstream request timed out" : "Upstream unavailable" },
      { status: timedOut ? 504 : 502 },
    );
  }
}

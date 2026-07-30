/** Authenticated, plot-scoped gateway for the internal drone service. */
import { NextRequest, NextResponse } from "next/server";
import { authorizePlot } from "@/lib/agribrain/authorize-plot";
import { parsePlotGeoJson } from "@/lib/agribrain/plot-geometry";

const AGRIBRAIN_URL = process.env.AGRIBRAIN_API_URL || "http://127.0.0.1:8000";
const SAFE_SEGMENT = /^[A-Za-z0-9_-]{1,128}$/;

type RouteKind =
  | "suggest-list"
  | "suggest-create"
  | "plan"
  | "dispatch"
  | "missions-list"
  | "mission-get"
  | "mission-control"
  | "mission-report";

function classifyPath(method: "GET" | "POST", path: string[]): RouteKind | null {
  if (!path.length || path.some((part) => !SAFE_SEGMENT.test(part))) return null;
  if (method === "GET" && path.length === 2 && path[0] === "suggest") return "suggest-list";
  if (method === "GET" && path.length === 1 && path[0] === "missions") return "missions-list";
  if (method === "GET" && path.length === 2 && path[0] === "missions") return "mission-get";
  if (method === "GET" && path.length === 3 && path[0] === "missions" && path[2] === "report") return "mission-report";
  if (method === "POST" && path.length === 1 && path[0] === "suggest") return "suggest-create";
  if (method === "POST" && path.length === 1 && path[0] === "plan") return "plan";
  if (method === "POST" && path.length === 1 && path[0] === "dispatch") return "dispatch";
  if (method === "POST" && path.length === 3 && path[0] === "missions" && path[2] === "control") return "mission-control";
  return null;
}

function errorResponse(status: number, error: string) {
  return NextResponse.json({ error }, { status });
}

async function forwardJson(url: string, init?: RequestInit) {
  try {
    const response = await fetch(url, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
      signal: AbortSignal.timeout(30_000),
    });
    const text = await response.text();
    const data = text ? JSON.parse(text) : null;
    return NextResponse.json(data, { status: response.status });
  } catch (error: unknown) {
    const timedOut = error instanceof Error && error.name === "TimeoutError";
    return errorResponse(timedOut ? 504 : 502, timedOut ? "Drone backend timed out" : "Drone backend unavailable");
  }
}

export async function GET(
  request: NextRequest,
  props: { params: Promise<{ path: string[] }> },
) {
  const { path } = await props.params;
  const kind = classifyPath("GET", path);
  if (!kind) return errorResponse(404, "Unsupported drone route");

  const requestedPlotId = kind === "suggest-list"
    ? path[1]
    : request.nextUrl.searchParams.get("plot_id");
  if (!requestedPlotId) return errorResponse(400, "plot_id is required");

  const access = await authorizePlot(requestedPlotId);
  if (!access.plot) {
    return errorResponse(access.status, access.status === 401 ? "Authentication required" : "Plot not found");
  }

  const query = new URLSearchParams();
  if (kind !== "suggest-list") query.set("plot_id", requestedPlotId);
  if (kind === "missions-list") {
    const requestedLimit = Number(request.nextUrl.searchParams.get("limit") || 20);
    query.set("limit", String(Number.isFinite(requestedLimit) ? Math.min(100, Math.max(1, Math.trunc(requestedLimit))) : 20));
  }
  const queryString = query.size ? `?${query.toString()}` : "";
  return forwardJson(`${AGRIBRAIN_URL}/api/drone/${path.join("/")}${queryString}`);
}

export async function POST(
  request: NextRequest,
  props: { params: Promise<{ path: string[] }> },
) {
  const { path } = await props.params;
  const kind = classifyPath("POST", path);
  if (!kind) return errorResponse(404, "Unsupported drone route");

  let body: Record<string, unknown>;
  try {
    body = await request.json();
  } catch {
    return errorResponse(400, "A JSON request body is required");
  }
  const plotId = body.plot_id;
  if (typeof plotId !== "string" || !plotId) return errorResponse(400, "plot_id is required");

  const access = await authorizePlot(plotId);
  if (!access.plot) {
    return errorResponse(access.status, access.status === 401 ? "Authentication required" : "Plot not found");
  }

  if (kind === "plan" || kind === "suggest-create") {
    const polygon = parsePlotGeoJson(access.plot.geoJson);
    if (!polygon) return errorResponse(422, "Plot has no authoritative polygon");
    body = { ...body, plot_id: plotId, polygon_geojson: polygon };
  } else {
    body = { ...body, plot_id: plotId };
  }

  return forwardJson(`${AGRIBRAIN_URL}/api/drone/${path.join("/")}`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

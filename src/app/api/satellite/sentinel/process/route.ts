import { NextRequest, NextResponse } from "next/server";
import { getAccessToken } from "@/lib/satellite-providers/sentinel-service";
import { authorizePlot } from "@/lib/agribrain/authorize-plot";
import { getPlotWgs84Bounds, isLocalPlotBounds, type Wgs84Bounds } from "@/lib/agribrain/plot-geometry";
import { EVALSCRIPTS } from "@/utils/evalscripts";
import { ObjectId } from "bson";

const ALLOWED_EVALSCRIPTS = new Set<string>(Object.values(EVALSCRIPTS));
const MAX_REQUEST_BYTES = 64 * 1024;
const MAX_RESPONSE_BYTES = 8 * 1024 * 1024;

export async function POST(req: NextRequest) {
  try {
    const declaredLength = Number(req.headers.get("content-length") || 0);
    if (declaredLength > MAX_REQUEST_BYTES) {
      return NextResponse.json({ error: "Request too large" }, { status: 413 });
    }
    const body = await req.json();
    if (JSON.stringify(body).length > MAX_REQUEST_BYTES) {
      return NextResponse.json({ error: "Request too large" }, { status: 413 });
    }

    const plotId = body?.plotId;
    if (typeof plotId !== "string" || !ObjectId.isValid(plotId)) {
      return NextResponse.json({ error: "Valid plotId is required" }, { status: 400 });
    }
    const authorization = await authorizePlot(plotId);
    if (!authorization.plot) {
      return NextResponse.json(
        { error: authorization.status === 401 ? "Authentication required" : "Plot not found" },
        { status: authorization.status },
      );
    }

    const bbox = body?.input?.bounds?.bbox;
    const data = body?.input?.data;
    const output = body?.output;
    const evalscript = body?.evalscript;
    const from = data?.[0]?.timeRange?.from;
    const to = data?.[0]?.timeRange?.to;
    const width = Number(output?.width);
    const height = Number(output?.height);
    const responseType = output?.responses?.[0]?.format?.type;
    const requestedBounds = Array.isArray(bbox) && bbox.length === 4
      ? bbox.map(Number) as Wgs84Bounds
      : null;
    const plotBounds = getPlotWgs84Bounds(authorization.plot.geoJson, {
      lat: Number(authorization.plot.farm.latitude),
      lng: Number(authorization.plot.farm.longitude),
    });
    const fromTime = typeof from === "string" ? Date.parse(from) : Number.NaN;
    const toTime = typeof to === "string" ? Date.parse(to) : Number.NaN;

    if (
      !requestedBounds
      || !plotBounds
      || !isLocalPlotBounds(requestedBounds, plotBounds)
      || !Array.isArray(data)
      || data.length !== 1
      || data[0]?.type !== "sentinel-2-l2a"
      || !Number.isFinite(fromTime)
      || !Number.isFinite(toTime)
      || fromTime > toTime
      || toTime - fromTime > 2 * 24 * 60 * 60 * 1000
      || fromTime < Date.UTC(2015, 0, 1)
      || toTime > Date.now() + 24 * 60 * 60 * 1000
      || !Number.isInteger(width)
      || width < 1
      || width > 512
      || !Number.isInteger(height)
      || height < 1
      || height > 512
      || responseType !== "image/png"
      || typeof evalscript !== "string"
      || !ALLOWED_EVALSCRIPTS.has(evalscript)
    ) {
      return NextResponse.json({ error: "Invalid or out-of-plot Sentinel request" }, { status: 400 });
    }

    const token = await getAccessToken();
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 20_000);

    const response = await fetch("https://sh.dataspace.copernicus.eu/api/v1/process", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: "image/png",
      },
      body: JSON.stringify({
        input: {
          bounds: {
            bbox: requestedBounds,
            properties: { crs: "http://www.opengis.net/def/crs/EPSG/0/4326" },
          },
          data: [{ type: "sentinel-2-l2a", timeRange: { from, to } }],
        },
        output: {
          width,
          height,
          responses: [{ identifier: "default", format: { type: "image/png" } }],
        },
        evalscript,
      }),
      signal: controller.signal,
    }).finally(() => clearTimeout(timeout));

    if (!response.ok) {
      console.error(`[Process API Proxy] CDSE request failed (${response.status})`);
      return NextResponse.json({ error: "Sentinel provider request failed" }, { status: 502 });
    }

    const contentType = response.headers.get("Content-Type") || "";
    const responseLength = Number(response.headers.get("content-length") || 0);
    if (!contentType.toLowerCase().startsWith("image/png") || responseLength > MAX_RESPONSE_BYTES) {
      return NextResponse.json({ error: "Invalid Sentinel provider response" }, { status: 502 });
    }
    const buffer = await response.arrayBuffer();
    if (buffer.byteLength > MAX_RESPONSE_BYTES) {
      return NextResponse.json({ error: "Sentinel provider response too large" }, { status: 502 });
    }
    
    return new NextResponse(buffer, {
      headers: {
        "Content-Type": "image/png",
        "Cache-Control": "private, max-age=300",
        "X-Content-Type-Options": "nosniff",
      },
    });
  } catch (error) {
    console.error("[Process API Proxy] Failed:", error);
    return new NextResponse("Internal Server Error", { status: 500 });
  }
}

import { NextRequest, NextResponse } from "next/server";
import { getAccessToken } from "@/lib/satellite-providers/sentinel-service";
import { authorizePlot } from "@/lib/agribrain/authorize-plot";
import { getPlotWgs84Bounds, isLocalPlotBounds, type Wgs84Bounds } from "@/lib/agribrain/plot-geometry";
import { ObjectId } from "bson";

const ALLOWED_WMS_KEYS = new Set([
  "SERVICE", "REQUEST", "LAYERS", "FORMAT", "TRANSPARENT", "VERSION",
  "CRS", "SRS", "BBOX", "WIDTH", "HEIGHT", "TIME", "STYLES", "TILED",
]);
const MAX_RESPONSE_BYTES = 8 * 1024 * 1024;

function webMercatorToWgs84(x: number, y: number): [number, number] {
  const radius = 6_378_137;
  const lng = x / radius * 180 / Math.PI;
  const lat = (2 * Math.atan(Math.exp(y / radius)) - Math.PI / 2) * 180 / Math.PI;
  return [lng, lat];
}

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const instanceId = process.env.SENTINEL_INSTANCE_ID;

  if (!instanceId) {
    return new NextResponse("Sentinel Instance ID not configured", { status: 400 });
  }

  // Construct CDSE WMS URL
  const cdseWmsUrl = new URL(`https://sh.dataspace.copernicus.eu/ogc/wms/${instanceId}`);
  
  // Create a case-insensitive parameter map for robust checks
  const params: Record<string, string> = {};
  searchParams.forEach((v, k) => params[k.toUpperCase()] = v);

  const plotId = params.PLOTID;
  if (!plotId || !ObjectId.isValid(plotId)) {
    return NextResponse.json({ error: "Valid plotId is required" }, { status: 400 });
  }
  const authorization = await authorizePlot(plotId);
  if (!authorization.plot) {
    return NextResponse.json(
      { error: authorization.status === 401 ? "Authentication required" : "Plot not found" },
      { status: authorization.status },
    );
  }

  const requestType = (params.REQUEST || "GETMAP").toUpperCase();
  const service = (params.SERVICE || "WMS").toUpperCase();
  const layer = (params.LAYERS || "S2L2A").toUpperCase();
  const crs = (params.CRS || params.SRS || "EPSG:3857").toUpperCase();
  const bboxValues = (params.BBOX || "").split(",").map(Number);
  const width = Number(params.WIDTH);
  const height = Number(params.HEIGHT);
  const timeText = params.TIME?.split("/")[0];
  const timeValue = timeText ? Date.parse(timeText) : Number.NaN;
  if (
    requestType !== "GETMAP"
    || service !== "WMS"
    || !["S2L2A", "SENTINEL2_L2A", "SENTINEL-2-L2A"].includes(layer)
    || crs !== "EPSG:3857"
    || bboxValues.length !== 4
    || bboxValues.some((value) => !Number.isFinite(value))
    || !Number.isInteger(width)
    || width < 1
    || width > 512
    || !Number.isInteger(height)
    || height < 1
    || height > 512
    || !Number.isFinite(timeValue)
    || timeValue < Date.UTC(2015, 0, 1)
    || timeValue > Date.now() + 24 * 60 * 60 * 1000
  ) {
    return NextResponse.json({ error: "Invalid Sentinel WMS request" }, { status: 400 });
  }

  const lowerLeft = webMercatorToWgs84(bboxValues[0], bboxValues[1]);
  const upperRight = webMercatorToWgs84(bboxValues[2], bboxValues[3]);
  const requestedBounds: Wgs84Bounds = [
    Math.min(lowerLeft[0], upperRight[0]),
    Math.min(lowerLeft[1], upperRight[1]),
    Math.max(lowerLeft[0], upperRight[0]),
    Math.max(lowerLeft[1], upperRight[1]),
  ];
  const plotBounds = getPlotWgs84Bounds(authorization.plot.geoJson, {
    lat: Number(authorization.plot.farm.latitude),
    lng: Number(authorization.plot.farm.longitude),
  });
  if (!plotBounds || !isLocalPlotBounds(requestedBounds, plotBounds)) {
    return NextResponse.json({ error: "WMS tile is outside the authorized plot vicinity" }, { status: 400 });
  }

  // Forward search parameters with robust mapping
  searchParams.forEach((value, key) => {
    const k = key.toUpperCase();
    
    // Skip managed keys and invalid values
    if (!ALLOWED_WMS_KEYS.has(k) || k === "VERSION" || value === "undefined" || !value) return;

    if (k === "CRS") {
      // Default to 1.1.1 (SRS) but we will finalize version below
      cdseWmsUrl.searchParams.set("SRS", value);
    } else if (k === "LAYERS") {
      // Standardize to S2L2A for CDSE if not already specified
      cdseWmsUrl.searchParams.set("LAYERS", "S2L2A");
    } else if (k === "STYLES") {
      cdseWmsUrl.searchParams.set("STYLES", "");
    } else if (value !== "") {
      cdseWmsUrl.searchParams.set(k, value);
    }
  });

  // Force WMS 1.3.0 for better CRS/BBOX handling in modern browsers
  cdseWmsUrl.searchParams.set("VERSION", "1.3.0");
  
  // Map back to CRS for 1.3.0
  if (cdseWmsUrl.searchParams.has("SRS")) {
    const srs = cdseWmsUrl.searchParams.get("SRS")!;
    cdseWmsUrl.searchParams.delete("SRS");
    cdseWmsUrl.searchParams.set("CRS", srs);
  }

  // Ensure mandatory 1.3.0 parameters
  if (!cdseWmsUrl.searchParams.has("STYLES")) {
    cdseWmsUrl.searchParams.set("STYLES", ""); 
  }
  if (!cdseWmsUrl.searchParams.has("FORMAT")) {
    cdseWmsUrl.searchParams.set("FORMAT", "image/png");
  }
  if (!cdseWmsUrl.searchParams.has("LAYERS")) {
    cdseWmsUrl.searchParams.set("LAYERS", "S2L2A");
  }

  try {
    const token = await getAccessToken();
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 20_000);

    const response = await fetch(cdseWmsUrl.toString(), {
      headers: {
        Authorization: `Bearer ${token}`,
      },
      signal: controller.signal,
    }).finally(() => clearTimeout(timeout));

    if (!response.ok) {
      console.error(`[WMS Proxy] CDSE request failed (${response.status})`);
      return NextResponse.json({ error: "Sentinel provider request failed" }, { status: 502 });
    }

    const contentType = response.headers.get("Content-Type") || "";
    const responseLength = Number(response.headers.get("content-length") || 0);
    if (!contentType.toLowerCase().startsWith("image/") || responseLength > MAX_RESPONSE_BYTES) {
      return NextResponse.json({ error: "Invalid Sentinel provider response" }, { status: 502 });
    }
    const buffer = await response.arrayBuffer();
    if (buffer.byteLength > MAX_RESPONSE_BYTES) {
      return NextResponse.json({ error: "Sentinel provider response too large" }, { status: 502 });
    }
    
    // Return with original content type (usually image/png or image/jpeg)
    return new NextResponse(buffer, {
      headers: {
        "Content-Type": contentType,
        "Cache-Control": "private, max-age=300",
        "X-Content-Type-Options": "nosniff",
      },
    });
  } catch (error) {
    console.error("[WMS Proxy] Failed:", error);
    return new NextResponse("Internal Server Error", { status: 500 });
  }
}

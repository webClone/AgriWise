import { NextRequest, NextResponse } from "next/server";
import { getAccessToken } from "@/lib/satellite-providers/sentinel-service";

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

  // Forward search parameters with robust mapping
  searchParams.forEach((value, key) => {
    const k = key.toUpperCase();
    
    // Skip managed keys and invalid values
    if (k === "VERSION" || k === "EVALSCRIPT" || value === "undefined" || !value) return;

    if (k === "CRS") {
      // Default to 1.1.1 (SRS) but we will finalize version below
      cdseWmsUrl.searchParams.set("SRS", value);
    } else if (k === "LAYERS") {
      // Standardize to S2L2A for CDSE if not already specified
      cdseWmsUrl.searchParams.set("LAYERS", (value === "SENTINEL2_L2A" || value === "sentinel-2-l2a") ? "S2L2A" : value);
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

    console.log("[WMS Proxy] Calling CDSE:", cdseWmsUrl.toString());

    const response = await fetch(cdseWmsUrl.toString(), {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error(`[WMS Proxy] CDSE ERROR (${response.status}):`, errorText);
      
      // If it's a 4xx error from CDSE, it's likely a bad request/unauthorized
      // Use the same status but wrap the message for clarity
      return new NextResponse(JSON.stringify({
        error: "Sentinel Hub Request Failed",
        details: errorText,
        cdseStatus: response.status,
        requestUrl: cdseWmsUrl.toString()
      }), { 
        status: response.status,
        headers: { "Content-Type": "application/json" }
      });
    }

    // Capture the image data
    const blob = await response.blob();
    
    // Return with original content type (usually image/png or image/jpeg)
    return new NextResponse(blob, {
      headers: {
        "Content-Type": response.headers.get("Content-Type") || "image/png",
        "Cache-Control": "public, max-age=3600, stale-while-revalidate=86400",
      },
    });
  } catch (error) {
    console.error("[WMS Proxy] Failed:", error);
    return new NextResponse("Internal Server Error", { status: 500 });
  }
}

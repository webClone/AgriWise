import { NextRequest, NextResponse } from "next/server";
import { getAccessToken } from "@/lib/satellite-providers/sentinel-service";

export async function POST(req: NextRequest) {
  try {
    const token = await getAccessToken();
    const body = await req.json();

    const response = await fetch("https://sh.dataspace.copernicus.eu/api/v1/process", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: req.headers.get("Accept") || "image/png",
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error(`[Process API Proxy] CDSE ERROR (${response.status}):`, errorText);
      return new NextResponse(errorText, { status: response.status });
    }

    const contentType = response.headers.get("Content-Type") || "image/png";
    const buffer = await response.arrayBuffer();
    
    return new NextResponse(buffer, {
      headers: {
        "Content-Type": contentType,
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    console.error("[Process API Proxy] Failed:", error);
    return new NextResponse("Internal Server Error", { status: 500 });
  }
}

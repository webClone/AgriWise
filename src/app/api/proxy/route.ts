import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = "http://127.0.0.1:8000";

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const path = searchParams.get("path");

  if (!path) {
    return NextResponse.json({ error: "Missing path parameter" }, { status: 400 });
  }

  // Construct target URL
  const targetUrl = new URL(path, BACKEND_URL);
  
  // Append all other query parameters
  searchParams.forEach((value, key) => {
    if (key !== "path") {
      targetUrl.searchParams.append(key, value);
    }
  });

  try {
    console.log(`[Proxy] Forwarding to: ${targetUrl.toString()}`);
    const response = await fetch(targetUrl.toString());
    
    if (!response.ok) {
        console.error(`[Proxy] Upstream error: ${response.status} ${response.statusText}`);
        return NextResponse.json(
            { error: `Upstream error: ${response.status}` }, 
            { status: response.status }
        );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("[Proxy] Request failed:", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}

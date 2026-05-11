import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { query, history } = body;

    const res = await fetch("http://127.0.0.1:8000/v2/intent", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        query: query || "",
        history: history ? JSON.stringify(history) : ""
      })
    });

    if (!res.ok) {
      throw new Error(`Intent API failed with status ${res.status}`);
    }

    const data = await res.json();
    return NextResponse.json({ success: true, data });
  } catch (e: any) {
    console.error("Intent routing error:", e);
    return NextResponse.json(
      { success: false, error: e.message || "Failed to route intent" },
      { status: 500 }
    );
  }
}
